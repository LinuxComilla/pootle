#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013 Zuza Software Foundation
#
# This file is part of Pootle.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

"""Extension action to generate Mozilla language packs (XPI)

This extension action uses the mozilla-l10n configuration files and repository
structure, but implements the necessary actions itself in Python, rather than
run the shell scripts that are provided in that Git repository.

"""

from __future__ import with_statement

import os
import shutil
from subprocess import CalledProcessError

from pootle.scripts.actions import DownloadAction, TranslationProjectAction

from moztarball import AURORA, getLogger, tempdir, get_phases, merge_po2moz
from buildxpi import build_xpi

logger = getLogger(__name__)


class MozillaLangpackAction(DownloadAction, TranslationProjectAction):
    """Download Mozilla language pack for Firefox"""

    def __init__(self, **kwargs):
        super(MozillaLangpackAction, self).__init__(**kwargs)
        self._waffle_flag = 'download_langpack'

    def run(self, path, root, tpdir,  # pylint: disable=R0913,R0914
            language, project, vc_root, **kwargs):
        """Generate a Mozilla language pack XPI"""

        with tempdir() as podir:
            try:
                get_phases(root, vc_root, podir, language, project)
            except (EnvironmentError, shutil.Error), e:
                logger.debug_exception(e)
                self.set_error(e)
                return

            with tempdir() as l10ndir:
                try:
                    merge_po2moz(vc_root, podir, l10ndir, language, project)
                except EnvironmentError, e:
                    logger.debug_exception(e)
                    self.set_error(e)
                    return

                source = os.path.join(vc_root, AURORA)

                def copyfile(filename):
                    """Copy a file from VC source to L10n build directory"""
                    split = filename.find(os.sep)
                    sourcefile = os.path.join(source, filename[:split],
                                              'locales/en-US',
                                              filename[split + 1:])
                    if os.path.exists(sourcefile):
                        destdir = os.path.join(l10ndir, language,
                                               os.path.dirname(filename))
                        basename = os.path.basename(filename)
                        if not os.path.isdir(destdir):
                            logger.debug("creating '%s' directory", destdir)
                            os.makedirs(destdir)
                        logger.debug("copying '%s' to '%s'", sourcefile,
                                     os.path.join(destdir, basename))
                        shutil.copy2(sourcefile, destdir)
                    else:
                        logger.warning('unable to find %s', sourcefile)

                def copyfileifmissing(filename):
                    """Copy a file only if needed."""
                    destfile = os.path.join(l10ndir, language, 'toolkit',
                                            filename)
                    if not os.path.exists(destfile):
                        copyfile(filename)

                try:
                    # from mozilla-l10n/.ttk/default/build.sh
                    copyfileifmissing('toolkit/chrome/mozapps/help/'
                                      'welcome.xhtml')
                    copyfileifmissing('toolkit/chrome/mozapps/help/'
                                      'help-toc.rdf')
                    copyfile('browser/firefox-l10n.js')
                    copyfile('browser/profile/chrome/userChrome-example.css')
                    copyfile('browser/profile/chrome/userContent-example.css')
                    copyfileifmissing('toolkit/chrome/global/intl.css')
                    # This one needs special approval but we need it
                    # to pass and compile
                    copyfileifmissing('browser/searchplugins/list.txt')

                    with tempdir() as xpidir:

                        xpifile = build_xpi(l10nbase=l10ndir, srcdir=source,
                                            outputdir=xpidir, langs=[language],
                                            product='browser')[0]

                        if xpifile:
                            newname = os.path.join(root, tpdir,
                                                   os.path.basename(xpifile))
                            logger.debug("copying '%s' to '%s'",
                                         xpifile, newname)
                            shutil.move(xpifile, newname)
                            self.set_error(self.set_download_file(path,
                                                                  newname))

                except (EnvironmentError, CalledProcessError), e:
                    logger.debug_exception(e)
                    self.set_error(e)
                    return


MozillaLangpackAction.moztar = MozillaLangpackAction(category="Other actions",
                                                     title="Download langpack")