#!/usr/bin/env python

#  Copyright 2001 Trustix As - <http://www.trustix.com>
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

VERSION = \
"SoftWare UPdater v0.1.7 - Copyright © 2001 Trustix"

HELP = \
"""Usage:	swup <operation> [option [...]]
OPERATIONS:
--help		This info.
--list-latest	List packages available from servers.
--list-new	Like list-latest, but only list not installed packages.
--version	Print version and copyright information.
--install	Install mode.
--upgrade	Upgrade mode.
--import-key	Import public key(s) from file.
--list-keys	List all public keys.
OPTIONS:
--verbose		Be somewhat more verbose.
--quiet			Be somewhat more quiet (overrides verbose).
--silent		Be silent (overrides quiet and verbose).
--no-flush-cache  	Don't flush the package cache.
--poll-only		Only check for new versions - use with --upgrade.
--download-only 	Download packages, but do not install.
--save-to dir		Store a copy of packages in dir.
--config-file file	Use "file" as config file.
--repository-URI URI	Override config file and use this URI for getting SPIs.
--package-URI URI [URI]	URIs to SPIs for packages to be installed.
--package-URI-file file Get above URI list from a newline separated file.
--package name [name]	Install packages with these shortnames (Ex: "vim").
--package-file file	Get package shortnames from a newline separated file.
--gnupg-dir dir		Use dir for storing files for signature checking.
--passwd-file file	Password file used for authentication over https.
--passwd pass [pass]	Supply password as above in the form user:pass@host"""

def version():
	print VERSION

def helpme():
	version()
	print HELP
