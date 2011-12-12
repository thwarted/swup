#!/usr/bin/python
# $Id: cmdline.py,v 1.28 2005/06/22 09:09:08 christht Exp $

# Validating quasi parser for command line options
#
#  Copyright 2001 - 2003 Trustix AS - <http://www.trustix.com>
#  Copyright 2003 - 2004 Tor Hveem - <tor@bash.no>
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

import sys
from swuplib import ex

# ugly hack 
# - O means "Operation". We need exactly one operation
# - a1 means "Takes _one_ argument"
# - a+ means "Takes one or more arguments"
# - a means "Takes zero or more arguments"

_SWITCHDICT = {
    "--config-file": "a1",
    "--config-option": "a1",
    "--copyright": "O",
    "--delete-key": "Oa1",
    "--describe": "Oa1",
    "--download-first": "",
    "--download-only": "",
    "--flush-cache": "O",
    "--force": "",
    "--gnupg-dir": "a1",
    "--help": "O",
    "--ignore-filter": "",
    "--ignore-lock": "",
    "--ignore-manual-upgrade": "",
    "--import-key": "Oa+",
    "--install": "Oa+",
    "--list-alien": "O",
    "--list-downgrade": "O",
    "--list-keys": "O",
    "--list-latest": "O",
    "--list-new": "O",
    "--list-prospect": "O",
    "--list-upgrade": "O",
    "--local-first": "",
    "--notty": "",
    "--package": "a+",
    "--package-URI": "a+",
    "--package-URI-file": "a1",
    "--package-file": "a1",
    "--poll-only": "",
    "--quiet": "",
    "--remove": "Oa+",
    "--remove-lock": "O",
    "--repository-URI": "a+",
    "--root": "a1",
    "--save-to": "a1",
    "--search-file": "Oa1",
    "--search-package": "Oa1",
    "--search-resource": "Oa1",
    "--silent": "",
    "--stage": "",
    "--status-file": "a1",
    "--upgrade": "Oa",
    "--verbose": "",
    "--version": "O",
    "--what-provides": "Oa1",
}


def validate (argdict):
    "Check the argument dictionary against the _SWITCHDICT."

    found_operation = False
    
    for key in argdict.keys():
        # if switch is not known, stop
        if key not in _SWITCHDICT.keys(): 
            raise ex.cmdline_unknown_error, key
                # --package is deprecated:
        if key == "--package":
            sys.stderr.write( 
                "Warning: Deprecated option '--package' ignored.\n")
            continue
                    
        
        if "O" in _SWITCHDICT[key]:
            # if we have more than one operation, stop
            if not found_operation == False:
                raise ex.too_many_operations_error, \
                    (found_operation, key)
            else: 
                found_operation = key	#set the operation found, only one operation at a time.

        if "a" in _SWITCHDICT[key]:
            # should the switch have arguments? how many?
            if "1" in _SWITCHDICT[key]:
                if len(argdict[key]) != 1:    #check for only one argument (a1)
                    raise ex.wrong_number_of_args_error, key
        
            if "+" in _SWITCHDICT[key]:
                if len(argdict[key]) < 1:  #check if arguments less than 1 for operation
                    if not argdict.has_key("--package"):
                        raise ex.wrong_number_of_args_error, key
                    if len(argdict["--package"]) < 1:
                        #if package switch(deprecated) is used? but no arguments passed
                        raise ex.wrong_number_of_args_error, key
                                        
        else:
            # the switch should not have arguments
            if len(argdict[key]) > 0:
                raise ex.wrong_number_of_args_error, key
    
    # at last, shout if we don't have an operation
    if found_operation == False:
        raise ex.too_few_operations_error, 'Need at least one operation'

def parse (args):
    """Parse command line arguments.
    
    Returns a dictionary with switches as keys and any switch arguments
    as key values. Will usually take sys.argv[1:] (everything but the)
    command name itself) as input.
    """
    
    # This Function takes argv passed : swup > swup.py (parse_argv) > swuplib/cmdline.py (parse)
    
    dict = {}    #initialize argument dictionary

    if not args:
        raise ex.cmdline_unknown_error, \
              'Missing arguments. Type swup --help for help.'

    if not args[0][0] == '-':    #checks if the argument passed is a command switch "-"
        raise ex.cmdline_unknown_error, args[0]
    
    for arg in args:
        if arg[0] == '-':
            switch = arg
            dict[switch] = []    
            #store switch as key for dict and also store key value as a List of values
            
        else:
            dict[switch].append(arg)    
            #store switch parameters as a List of values corresponding to the key
            #e.g. {'--package': ['package1.rpm', 'package2.rpm', 'package3.rpm'], '--download-only': []}
    
    validate(dict)
    #passes the dict with switches and switch arguments to validate function
    #which check for validity of the switch and the number of arguments to the switch.

    return dict #returns the validated arguments as a dictionary "dict".

