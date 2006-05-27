# Copyright 2006 Joe Wreschnig <piman@sacredchao.net>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# $Id$

"""Read and write Ogg bitstreams and pages.

This module reads and writes a subset of the Ogg bitstream format
version 0. It does *not* read or write Ogg Vorbis files! For that,
you should use mutagen.oggvorbis.

This implementation is based on the RFC 3533 standard found at
http://www.xiph.org/ogg/doc/rfc3533.txt.
"""

import struct
import sys
import zlib

from cStringIO import StringIO

from mutagen import FileType
from mutagen._util import cdata, insert_bytes, delete_bytes

class error(IOError):
    """Ogg stream parsing errors."""
    pass

class OggPage(object):
    """A single Ogg page (not necessarily a single encoded packet).

    A page is a header of 26 bytes, followed by the length of the
    data, followed by the data.

    The constructor is givin a file-like object pointing to the start
    of an Ogg page. After the constructor is finished it is pointing
    to the start of the next page.

    Attributes:
    version -- stream structure version (currently always 0)
    position -- absolute stream position (default -1)
    serial -- logical stream serial number (default 0)
    sequence -- page sequence number within logical stream (default 0)
    offset -- offset this page was read from (default None)
    complete -- if the last packet on this page is complete (default True)
    packets -- list of raw packet data (default [])

    Note that if 'complete' is false, the next page's 'continued'
    property must be true (so set both when constructing pages).

    If a file-like object is supplied to the constructor, the above
    attributes will be filled in based on it.
    """

    version = 0
    __type_flags = 0
    position = -1L
    serial = 0
    sequence = 0
    offset = None
    complete = True

    def __init__(self, fileobj=None):
        self.packets = []

        if fileobj is None:
            return

        self.offset = fileobj.tell()

        header = fileobj.read(27)
        if len(header) == 0:
            raise EOFError
        (oggs, self.version, self.__type_flags, self.position,
         self.serial, self.sequence, crc, segments) = struct.unpack(
            "<4sBBqIIiB", header)

        if oggs != "OggS":
            raise error("read %r, expected %r, at 0x%x" % (
                oggs, "OggS", fileobj.tell() - 27))

        if self.version != 0:
            raise error("version %r unsupported" % self.version)

        total = 0
        lacings = []
        lacing_bytes = fileobj.read(segments)
        if len(lacing_bytes) != segments:
            raise error("unable to read %r lacing bytes" % segments)
        for c in map(ord, lacing_bytes):
            total += c
            if c < 255:
                lacings.append(total)
                total = 0
        if total:
            lacings.append(total)
            self.complete = False

        self.packets = map(fileobj.read, lacings)
        if map(len, self.packets) != lacings:
            raise error("unable to read full data")

    def __eq__(self, other):
        """Two Ogg pages are the same if they write the same data."""
        try:
            return (self.write() == other.write())
        except AttributeError:
            return False

    def __repr__(self):
        attrs = ['version', 'position', 'serial', 'sequence', 'offset',
                 'complete', 'continued', 'first', 'last']
        values = ["%s=%r" % (attr, getattr(self, attr)) for attr in attrs]
        return "<%s %s, %d bytes in %d packets>" % (
            type(self).__name__, " ".join(values), sum(map(len, self.packets)),
            len(self.packets))

    def write(self):
        """Return a string encoding of the page header and data.

        A ValueError is raised if the data is too big to fit in a
        single page.
        """

        data = [
            struct.pack("<4sBBqIIi", "OggS", self.version, self.__type_flags,
                        self.position, self.serial, self.sequence, 0)
            ]

        lacing_data = []
        for datum in self.packets:
            quot, rem = divmod(len(datum), 255)
            lacing_data.append("\xff" * quot + chr(rem))
        lacing_data = "".join(lacing_data)
        if not self.complete and lacing_data.endswith("\x00"):
            lacing_data = lacing_data[:-1]
        data.append(chr(len(lacing_data)))
        data.append(lacing_data)
        data.extend(self.packets)
        data = "".join(data)

        # Python's CRC is swapped relative to Ogg's needs.
        crc = ~zlib.crc32(data.translate(cdata.bitswap), -1)
        # Although we're using to_int_be, this actually makes the CRC
        # a proper le integer, since Python's CRC is byteswapped.
        crc = cdata.to_int_be(crc).translate(cdata.bitswap)
        data = data[:22] + crc + data[26:]
        return data

    def __size(self):
        size = 27 # Initial header size
        for datum in self.packets:
            quot, rem = divmod(len(datum), 255)
            size += quot + 1
        if not self.complete and rem == 0:
            # Packet contains a multiple of 255 bytes and is not
            # terminated, so we don't have a \x00 at the end.
            size -= 1
        size += sum(map(len, self.packets))
        return size

    size = property(__size, doc="Total frame size.")

    def __set_flag(self, bit, val):
        mask = 1 << bit
        if val: self.__type_flags |= mask
        else: self.__type_flags &= ~mask

    continued = property(
        lambda self: cdata.test_bit(self.__type_flags, 0),
        lambda self, v: self.__set_flag(0, v),
        doc="The first packet is continued from the previous page.")

    first = property(
        lambda self: cdata.test_bit(self.__type_flags, 1),
        lambda self, v: self.__set_flag(1, v),
        doc="This is the first page of a logical bitstream.")

    last = property(
        lambda self: cdata.test_bit(self.__type_flags, 2),
        lambda self, v: self.__set_flag(2, v),
        doc="This is the last page of a logical bitstream.")

    def renumber(klass, fileobj, serial, start):
        """Renumber pages belonging to a specified logical stream.

        fileobj must be opened with mode rb+ or equivalent.

        Starting at page number 'start', renumber all pages belonging
        to logical stream 'serial'. Other pages will be ignored.

        fileobj must point to the start of a valid Ogg page; any
        occuring after it and part of the specified logical stream
        will be numbered. No adjustment will be made to the data in
        the pages nor the granule position; only the page number, and
        so also the CRC.

        If an error occurs (e.g. non-Ogg data is found), fileobj will
        be left pointing to the place in the stream the error occured,
        but the invalid data will be left intact (since this function
        does not change the total file size).
        """

        number = start
        while True:
            try: page = OggPage(fileobj)
            except EOFError:
                break
            else:
                if page.serial != serial:
                    # Wrong stream, skip this page.
                    continue
                # Changing the number can't change the page size,
                # so seeking back based on the current size is safe.
                fileobj.seek(-page.size, 1)
            page.sequence = number
            fileobj.write(page.write())
            number += 1
    renumber = classmethod(renumber)

    def to_packets(klass, pages, strict=False):
        """Construct a list of packet data from a list of Ogg pages.

        If strict is true, the first page must start a new packet,
        and the last page must end the last packet.
        """

        serial = pages[0].serial
        sequence = pages[0].sequence

        if strict:
            if pages[0].continued:
                raise ValueError("first packet is continued")
            if not pages[-1].complete:
                raise ValueError("last packet does not complete")

        packets = []
        for page in pages:
            if serial != page.serial:
                raise ValueError("invalid serial number in %r" % page)
            elif sequence != page.sequence:
                raise ValueError("bad sequence number in %r" % page)
            else: sequence += 1

            if page.continued: packets[-1] += page.packets[0]
            else: packets.append(page.packets[0])
            packets.extend(page.packets[1:])

        return packets
    to_packets = classmethod(to_packets)

    def from_packets(klass, packets, sequence=0):
        """Construct a list of Ogg pages from a list of packet data.

        The exact packet/page segmentation chosen by this function is
        undefined, except it will be within Ogg specifications.
        Currently, it generates pages approximately 4kb in size,
        in accordance with the specification's recommendations.

        Pages are numbered started at 'sequence'; other information is
        uninitialized.
        """

        pages = []

        page = OggPage()
        page.sequence = sequence
        for packet in packets:
            page.packets.append("")
            while packet:
                data, packet = packet[:2040], packet[2040:]
                # FIXME: Building strings like this is ridiculously
                # slow (though it's probably dominated by the cost of
                # file access for any real Ogg handling).
                if page.size < 4096 and len(page.packets) < 255:
                    page.packets[-1] += data
                else:
                    page.complete = False
                    pages.append(page)
                    page = OggPage()
                    page.continued = True
                    page.sequence = pages[-1].sequence + 1
                    page.packets.append(data)

        if page.packets:
            pages.append(page)

        return pages
    from_packets = classmethod(from_packets)

    def replace(klass, fileobj, old_pages, new_pages):
        """Replace old_pages with new_pages within fileobj.

        old_pages must have come from reading fileobj originally.
        new_pages are assumed to have the 'same' data as old_pages,
        and so the serial and sequence numbers will be copied, as will
        the flags for the first and last pages.

        fileobj will be resized and pages renumbered as necessary.
        """

        # Number the new pages starting from the first old page.
        first = old_pages[0].sequence
        for page, seq in zip(new_pages, range(first, first + len(new_pages))):
            page.sequence = seq
            page.serial = old_pages[0].serial

        new_pages[0].first = old_pages[0].first
        new_pages[0].last = old_pages[0].last
        new_pages[0].continued = old_pages[0].continued

        new_pages[-1].first = old_pages[-1].first
        new_pages[-1].last = old_pages[-1].last
        new_pages[-1].complete = old_pages[-1].complete

        new_data = "".join(map(klass.write, new_pages))

        # Make room in the file for the new data.
        delta = len(new_data)
        fileobj.seek(old_pages[0].offset, 0)
        insert_bytes(fileobj, delta, old_pages[0].offset)
        fileobj.seek(old_pages[0].offset, 0)
        fileobj.write(new_data)
        new_data_end = fileobj.tell()

        # Go through the old pages and delete them. Since we shifted
        # the data down the file, we need to adjust their offsets. We
        # also need to go backwards, so we don't adjust the deltas of
        # the other pages.
        old_pages.reverse()
        for old_page in old_pages:
            adj_offset = old_page.offset + delta
            delete_bytes(fileobj, old_page.size, adj_offset)

        # Finally, if there's any discrepency in length, we need to
        # renumber the pages for the logical stream.
        if len(old_pages) != len(new_pages):
            fileobj.seek(new_data_end, 0)
            serial = new_pages[-1].serial
            sequence = new_pages[-1].sequence + 1
            klass.renumber(fileobj, serial, sequence)
    replace = classmethod(replace)

    def find_last(klass, fileobj, serial):
        """Find the last page of the stream 'serial'.

        If the file is not multiplexed this function is fast. If it is,
        it must read the whole the stream.
        """

        # For non-muxed streams, look at the last page.
        try: fileobj.seek(-256*256, 2)
        except IOError:
            # The file is less than 64k in length.
            fileobj.seek(0)
        data = fileobj.read()
        try: index = data.rindex("OggS")
        except ValueError:
            raise error("unable to find final Ogg header")
        stringobj = StringIO(data[index:])
        page = OggPage(stringobj)
        if page.serial == serial:
            return page
        else:
            # The stream is muxed, so use the slow way.
            fileobj.seek(0)
            page = OggPage(fileobj)
            while not page.last:
                while page.serial != serial:
                    page = OggPage(fileobj)
            return page
    find_last = classmethod(find_last)

class OggFileType(FileType):
    """An generic Ogg file."""

    _Info = None
    _Tags = None
    _Error = None

    def __init__(self, filename=None):
        if filename:
            self.load(filename)

    def load(self, filename):
        """Load file information from a filename."""

        self.filename = filename
        fileobj = file(filename, "rb")
        try:
            try:
                self.info = self._Info(fileobj)
                self.tags = self._Tags(fileobj, self.info)

                if self.info.length:
                    # The streaminfo gave us real length information,
                    # don't waste time scanning the Ogg.
                    return

                last_page = OggPage.find_last(fileobj, self.info.serial)
                samples = last_page.position
                self.info.length = samples / float(self.info.sample_rate)

            except error, e:
                raise self._Error, e, sys.exc_info()[2]
        finally:
            fileobj.close()

    def delete(self, filename=None):
        """Remove tags from a file.

        If no filename is given, the one most recently loaded is used.
        """
        if filename is None:
            filename = self.filename

        self.tags.clear()
        fileobj = file(filename, "rb+")
        try:
            try: self.tags._inject(fileobj)
            except IOError, e:
                raise self._Error, e, sys.exc_info()[2]
        finally:
            fileobj.close()

    def save(self, filename=None):
        """Save a tag to a file.

        If no filename is given, the one most recently loaded is used.
        """
        if filename is None:
            filename = self.filename
        self.tags.validate()
        fileobj = file(filename, "rb+")
        try:
            try: self.tags._inject(fileobj)
            except error, e:
                raise self._Error(e)
        finally:
            fileobj.close()