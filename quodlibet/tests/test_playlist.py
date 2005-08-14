from unittest import TestCase, makeSuite
from tests import registerCase
from songlist import PlaylistModel, QueueModel

class Queue(TestCase):
    def setUp(self):
        self.q = QueueModel()
        self.q.extend(range(10))

    def test_isempty(self):
        self.failIf(self.q.is_empty())
        self.q.clear()
        self.failUnless(self.q.is_empty())

    def test_get(self):
        self.assertEquals(self.q.get(), 0)
        self.assertEquals(self.q.get(), 1)
        self.assertEquals(self.q.get(), 2)
        self.assertEquals(self.q.get(), 3)
        self.assertEquals(self.q.get(), 4)

    def test_remove(self):
        self.assertEquals(self.q.get(), 0)
        self.q.remove_song(1)
        self.assertEquals(self.q.get(), 2)
        self.assertEquals(self.q.get(), 3)

    def test_goto(self):
        self.assertEquals(self.q.get(), 0)
        self.q.go_to(3)
        self.assertEquals(self.q.get(), 3)
        self.assertEquals(self.q.get(), 1)
        self.assertEquals(self.q.get(), 2)
        self.assertEquals(self.q.get(), 4)

    def test_shuffle(self):
        self.q.shuffle = 1
        numbers = [self.q.get() for i in range(10)]
        self.assertNotEquals(numbers, range(10))
        numbers.sort()
        self.assertEquals(numbers, range(10))

    def shutDown(self):
        self.q.destroy()

class Playlist(TestCase):
    def setUp(self):
        self.pl = PlaylistModel()
        self.pl.set(range(10))
        self.failUnless(self.pl.current is None)

    def test_isempty(self):
        self.failIf(self.pl.is_empty())
        self.pl.clear()
        self.failUnless(self.pl.is_empty())

    def test_get(self):
        self.assertEqual(self.pl.get(), range(10))
        self.pl.set(range(12))
        self.assertEqual(self.pl.get(), range(12))

    def test_next(self):
        self.pl.next()
        self.failUnlessEqual(self.pl.current, 0)
        self.pl.next()
        self.failUnlessEqual(self.pl.current, 1)
        self.pl.go_to(9)
        self.failUnlessEqual(self.pl.current, 9)
        self.pl.next()
        self.failUnless(self.pl.current is None)

    def test_next_repeat(self):
        self.pl.repeat = True
        self.pl.go_to(3)
        for i in range(9): self.pl.next()
        self.assertEqual(self.pl.current, 2)
        for i in range(12): self.pl.next()
        self.assertEqual(self.pl.current, 4)

    def test_shuffle(self):
        self.pl.shuffle = 1
        for i in range(5):
            numbers = [self.pl.current for i in range(10)
                       if self.pl.next() or True]
            self.assertNotEqual(numbers, range(10))
            numbers.sort()
            self.assertEqual(numbers, range(10))
            self.pl.next()
            self.assertEqual(self.pl.current, None)

    def test_weighted_shuffle(self):
        self.pl.shuffle = 2
        r0 = {'~#rating': 0}
        r1 = {'~#rating': 1}
        r2 = {'~#rating': 2}
        r3 = {'~#rating': 3}
        self.pl.set([r0, r1, r2, r3])
        songs = [self.pl.current for i in range(1000)
                 if self.pl.next() or True]
        self.assert_(songs.count(r1) > songs.count(r0))
        self.assert_(songs.count(r2) > songs.count(r1))
        self.assert_(songs.count(r3) > songs.count(r2))

    def test_shuffle_repeat(self):
        self.pl.shuffle = 1
        self.pl.repeat = True
        numbers = [self.pl.current for i in range(30)
                   if self.pl.next() or True]
        allnums = range(10) * 3
        allnums.sort()
        self.assertNotEqual(numbers, allnums)
        numbers.sort()
        self.assertEqual(numbers, allnums)

    def test_previous(self):
        self.pl.go_to(2)
        self.failUnlessEqual(self.pl.current, 2)
        self.pl.previous()
        self.failUnlessEqual(self.pl.current, 1)
        self.pl.previous()
        self.failUnlessEqual(self.pl.current, 0)
        self.pl.previous()
        self.failUnlessEqual(self.pl.current, 0)

    def test_go_to_saves_current(self):
        self.pl.go_to(5)
        self.failUnlessEqual(self.pl.current, 5)
        self.pl.set([5, 10, 15, 20])
        self.pl.next()
        self.failUnlessEqual(self.pl.current, 10)

    def test_go_to_shuffle(self):
        self.pl.shuffle = 1
        for i in range(5):
            self.pl.go_to(5)
            self.failUnlessEqual(self.pl.current, 5)
            self.pl.go_to(1)
            self.failUnlessEqual(self.pl.current, 1)

    def test_go_to_none(self):
        self.pl.shuffle = 1
        for i in range(5):
            self.pl.go_to(None)
            self.failUnlessEqual(self.pl.current, None)
            self.pl.next()
            self.failUnlessEqual(self.pl.current, 0)

    def test_reset(self):
        self.pl.go_to(5)
        self.failUnlessEqual(self.pl.current, 5)
        self.pl.reset()
        self.failUnlessEqual(self.pl.current, None)
        self.pl.next()
        self.failUnlessEqual(self.pl.current, 0)

    def test_reset_shuffle(self):
        self.pl.shuffle = 1
        self.pl.go_to(5)
        self.failUnlessEqual(self.pl.current, 5)
        self.pl.reset()
        self.failUnlessEqual(self.pl.current, None)
        self.pl.next()
        self.failUnlessEqual(self.pl.current, 0)

    def test_restart(self):
        self.pl.go_to(1)
        self.pl.set([101, 102, 103, 104])
        self.pl.next()
        self.failUnlessEqual(self.pl.current, 101)

    def shutDown(self):
        self.pl.destroy()

registerCase(Playlist)
registerCase(Queue)
