#!/usr/bin/python
# $Id: help.py,v 1.100 2005/08/12 13:19:45 christht Exp $

#  Copyright 2001 - 2004 Comodo Trustix Ltd - <http://www.trustix.com>
#  Copyright 2003 - 2004 Tor Hveem - <tor@bash.no>
#  Copyright 2004 Omar Kilani for tinysofa - <http://www.tinysofa.org>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

VERSION="2.7.15"

SWUP_VERSION = "SoftWare UPdater v%s" %VERSION

SWUP_COPYRIGHT = \
"Copyrights:\n\
Comodo Trustix Ltd. (C) 2001 - 2005\n\
Christian H. Toldnes (C) 2003\n\
Tor Hveem (C) 2003 - 2004\n\
Omar Kilani (C) 2004"

RDFGEN_VERSION = 'RDF Generator - part of %s' %SWUP_VERSION

SWUP_HELP = \
"""Usage:       swup <operation> [option [...]] [args]
OPERATIONS:
--install <package(s)>  Installs the given package(s) and their requirements.
                        Package arguments can be regular expressions.
--upgrade [package(s)]  Upgrade the system, or just given package(s)
                        Package arguments can be regular expressions.
--remove <package(s)>   Remove the given package(s), including packages that
                        depends upon package(s) given. Is recursive.
--list-latest           List all packages available from servers
--list-new              Like list-latest, but only list those not installed
--list-alien            List packages that are alien compared to the 
                        configured repositories
--list-downgrade        List packages that have a higher local version than   
                        remote compared to the configured repositories
--list-upgrade          List packages that would be installed in upgrade mode
--search-file           List package(s), providing file(s) matching a pattern
--search-package        Search for package(s), if name matching a pattern
--search-resource       Search for resource(s), if name matching a pattern
--describe              Show detailed description of a package
--what-provides         Lists packages that provides given resourcename
--import-key            Import public key(s) from file(s)
--delete-key            Delete imported public key
--list-keys             List imported public key(s)
--help                  This info
--version               Print version
--copyright             Print copyright information
OPTIONS:
--config-file file      Use "file" as config file
--config-option option  Use "option" as additional configuration option.
                        (e.g. --config-option "exclude_pkg_regexp = 'swup.*'")
                        (Not implemented yet.)
--download-first        First download packages to cache, then install
--download-only         Download packages to cache, but do not install
--force                 Force to continue in spite of warnings. Currently
                        enforces operation on warnings:
                        - Removing package 'swup' not permitted.
                        - Manual upgrade required.
--gnupg-dir dir         Use dir for storing files for signature checking
--ignore-filter         Ignore the exclude/include statements in the config
--ignore-manual-upgrade (Obsoleted by --force)
--notty                 Run as if stdout is not a tty. (overrides verbose)
--package-file file     Get package shortnames from a newline separated file
--poll-only             Only check for new versions - use with --upgrade
--quiet                 Be somewhat more quiet (overrides notty and verbose)
--repository-URI URI    Use  Uniform  Resource Allocator to file that contains
                        a list of latest packages.  This will override the list
                        of default URIs in configuration  file.  Protocols
                        file,  http, https, and ftp are supported. One or
                        several URIs may be submitted, first URI takes
                        precedence over the next URI.
--root dir              Use dir as rpm root (similar to rpm --root)
--save-to dir           Store a copy of packages in dir
--silent                Be totally silent (overrides notty, quiet and verbose)
--stage                 Install using stages, implies --download-first
--verbose               Be somewhat more verbose
DEBUG OPERATIONS:
--flush-cache           Empty cachedir
--local-first           Prefer already installed resource during resolving
--remove-lock           Remove lockfile
DEBUG OPTIONS:
--ignore-lock           Do not care about lockfile
"""

RDFGEN_HELP = \
"""Usage:       rdfgen [operation] [option [...]] [args]
OPERATIONS:
-h, --help              print this message.
-v, --version           Print version.
OPTIONS:
-C, --nocompress        Do not compress files.
-L <BASEURI>            Link against remote repository given by <URI>.
                        URI must end with a trailing "/" and determins where to
                        find resources.rdf ( or resourcelist.rdf ) and filelist.
                        http:// https:// and ftp:// are supported protocols.
-P <filename>           Read password from given <filename>.
-S, --sign              Sign created files.
-b                      Generate backward compatible rdf tree.
-g <homedir>            Use given <homedir> as gpg homedir.
-k <keyid>              Sign with given <keyid>.
-o <dir>                directory to where rdfs are written.
-q, --quiet             Print as little as possible.
-s <dir>                directory to where package signatures are written.
"""


def version(SWUP=True):
    if SWUP:
        print SWUP_VERSION
    else:
        print RDFGEN_VERSION

def copyright():
    print SWUP_COPYRIGHT

def helpme(SWUP=True):
    version(SWUP)
    if SWUP:        
        print SWUP_HELP
    else:
        print RDFGEN_HELP

