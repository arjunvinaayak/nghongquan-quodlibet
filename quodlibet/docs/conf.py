# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, os.path.abspath('../'))
from quodlibet import const

extensions = ['sphinx.ext.autodoc']
source_suffix = '.rst'
master_doc = 'index'
project = 'Ex Falso / Quod Libet'
copyright = 'The Quod Libet Devs'
version = ".".join(const.VERSION.rsplit(".")[:2])
release = const.VERSION
if release.endswith(".-1"):
    release = release[:-3]
exclude_patterns = ['_build']
html_theme = "haiku"
html_title = "%s (%s)" % (project, version)

RTD_NEW_THEME = True
