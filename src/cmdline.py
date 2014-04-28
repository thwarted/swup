#!/usr/bin/env python
#
# Validating quasi parser for command line options
#

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

true, false = 1, 0

unknown = 'cmdline.unknown'
wrong_number_arguments = 'cmdline.wrong_number_arguments'
too_few_operations = 'cmdline.too_few_operations'
too_many_operations = 'cmdline.too_many_operations'

general_error = \
(unknown, wrong_number_arguments, too_few_operations, too_many_operations)

# ugly hack 
# - O means "Operation". We need exactly one operation
# - a means "Takes _one_ argument"
# - A means "Takes one or more arguments"

_SWITCHDICT = {
	"--help": "O",
	"--version": "O",
	"--install": "O",
	"--upgrade": "O",
	"--import-key": "Oa1",
	"--list-keys": "O",
	"--list-latest": "O",
	"--quiet": "",
	"--verbose": "",
	"--silent": "",
	"--no-flush-cache": "",
	"--poll-only": "",
	"--download-only": "",
	"--config-file": "a1",
	"--repository-URI": "a1",
	"--package-URI": "a+",
	"--package-URI-file": "a1",
	"--package": "a+",
	"--package-file": "a1",
	"--gnupg-dir": "a1",
	"--save-to": "a1",
	"--list-new": "O"
}


def validate (argdict):
	"Check the argument dictionary against the _SWITCHDICT."

	found_operation = false
	
	for key in argdict.keys():
		# if switch is not known, stop
		if key not in _SWITCHDICT.keys(): 
			raise unknown, key
		
		if "O" in _SWITCHDICT[key]:
			# if we have more than one operation, stop
			if not found_operation == false:
				raise too_many_operations, \
					(found_operation, key)
			else: 
				found_operation = key

		if "a" in _SWITCHDICT[key]:
			# should the switch have arguments? how many?
			if "1" in _SWITCHDICT[key]:
				if len(argdict[key]) != 1:
					raise wrong_number_arguments, key
		
			if "+" in _SWITCHDICT[key]:
				if len(argdict[key]) < 1:
					raise wrong_number_arguments, key

		else:
			# the switch should not have arguments
			if len(argdict[key]) > 0:
				raise wrong_number_arguments, key
	
	# at last, shout if we don't have an operation
	if found_operation == false:
		raise too_few_operations, 'Need at least one operation'

def parse (args):
	"""Parse command line arguments.
	
	Returns a dictionary with switches as keys and any switch arguments
	as key values. Will usually take sys.argv[1:] (everything but the)
	command name itself) as input.
	"""

	dict = {}

	if not args:
		raise unknown, \
		      'Missing arguments. Type swup --help for help.'

	if not args[0][0] == '-':
		raise unknown, args[0]
	
	for arg in args:
		if arg[0] == '-':
			switch = arg
			dict[switch] = []
		else:
			dict[switch].append(arg)
	
	validate(dict)

	return dict

