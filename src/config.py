# $Id: config.py,v 1.7 2001/06/18 13:08:39 olafb Exp $
"""Module contains main function 'parse(filename=None)' for parsing
config for swup. Function returns a dictionary of config variables. If
a valid optional filename is given, variables defined in file will
override the corresponding default variables.
"""

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


import shlex, os

# defaults
DEFAULT_CONFIG_FILE = "/etc/swup/swup.conf"
DEFAULT_CONFIG = {
"driver": "pkgdriver.rpmdriver",
"logfile": "/var/log/swup",
"gnupgdir": "/etc/swup/gnupg",
"dependency_maxdept": 5,
"cachedir": "/var/cache/swup",
"interactive_logged": "yes",
"download_only": "no",
"save_to":  "",
"poll_only": "no",
"dry_run": "no",
"listsdir": "/var/cache/swup/lists",
"md5sumfile": "/var/cache/swup/lists/md5sums",
"tmpdir": "/var/spool/swup",
"flush_cache": "yes",
"sites": [(0,
         "ftp://ftp.trustix.net/pub/Trustix/trustix-1.2/i586/Trustix/rdfs/latest.rdf"
         ".*")],
"exclude_pkg_regexp": "kernel.*",
"exclude_group_regexp": "",
"include_pkg_regexp": "",
"include_group_regexp": ".*"
}



class ConfigError(Exception): pass
class ConfigIOError(ConfigError): pass

class ConfigParseError(ConfigError):
    def __init__(self, filename, config, msg=None):
        self.file = filename
        self.lineno = config.lineno
        self.token = config.token
        self.msg = msg

    def __str__(self):
        msg = 'Error in ' + self.file + ', line ' + str(self.lineno)
        if self.token != "":
            msg = msg + " near '" + self.token + "'"
        msg = msg + ": " + self.msg
        return msg

class ConfigBadOptionError:
    def __init__(self, option):
        self.option = option

    def __str__(self):
        return 'Unrecognized option ' + self.option

class ConfigMissingOptionError:
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg

class ConfigSection:
    def __init__(self, type):
        self.type = type
        self.options = {}

    def __str__(self):
        return str(self.options)

    def set(self, option, value):
        if option == "priority":
            self.options[option] = int(value)
        elif option in ["regexp", "location"]:
            self.options[option] = str(value)
        else:
            raise ConfigBadOptionError( option )

    def getType(self):
        return self.type

    def validate(self):
        """This function makes sure that all required options are set."""
        keys = self.options.keys()
        if not 'location' in keys:
            raise ConfigMissingOptionError("Missing URL for site.")
        if not 'regexp' in keys:
            self.set("regexp", ".*")
        if not 'priority' in keys:
            self.set("priority", 0)
            
    def __len__(self):
        return len(self.options)

    def __getitem__(self, key):
        return self.options[key]

    def has_key(self, key):
        return self.options.has_key(key)

    def values(self):
        return self.options.values()

    def __delitem__(self, key):
        del self.options[key]

    def update(self, dict):
        self.options.update(dict)


class ConfigParser:
    def __init__(self):
        self.options = {}
        self.sections = []

    def stripQuotes(self, text):
        if len(text) > 1:
            if text[0] == '"' and text[-1] == '"' \
               or text[0] == "'" and text[-1] == "'":
                return text[1:-1]
        return text

    def addOption(self, option, value):
        # TODO: Validate type and possibly raise exception if
        # the option is unknown

        self.options[option] = self.stripQuotes(value)

    def parse(self, filename):
        try:
            fd = open(filename)
        except IOError:
            raise ConfigIOError, 'Unable to open config file %s' % filename
        config = shlex.shlex(fd)
        finished = 0
        state = '-'
        option = None
        section = None
        while not finished:
            token = config.get_token()
            if token == "":
                finished = 1
            else:
                if state == '-':
                    # reading option name
                    option = token
                    state = 'O'

                elif state == 'O':
                    # next token should be '=' for assignment, or
                    # '{' to start a section
                    if token == '=':
                        state = '='
                    elif token == '{':
                        if option != "site":
                            raise ConfigParseError(filename, config, "Unrecognized section " + option)
                        state = '{'
                        section = ConfigSection(option)
                    else:
                        raise ConfigParseError(filename, config, "Expecting '=' or '{'")

                elif state == '=':
                    # next token is the value of the option
                    self.addOption( option, token )
                    option = None
                    state = '-'

                elif state == '{':
                    # next token should be an option in the section,
                    # or '}' to finish the section
                    if token == '}':
                        try:
                            section.validate()
                            self.sections.append(section)
                            section = None
                        except ConfigMissingOptionError, e:
                            raise ConfigParseError(filename, config, e.__str__())
                        state = '-'
                    else:
                        option = token
                        state = '{O'

                elif state == '{O':
                    # next token should be '=' for assignment
                    if token == '=':
                        state = '{='
                    else:
                        raise ConfigParseError(filename, config, "Expecting '='")

                elif state == '{=':
                    # next token is the value of the option
                    try:
                        section.set(option, self.stripQuotes(token))
                    except ConfigBadOptionError, e:
                        raise ConfigParseError(filename, config, e.__str__())
                    option = None
                    state = '{'
        fd.close()
        
    def getSections(self):
        return self.sections

    def getOptions(self):
        return self.options

def parse(filename=None):
    config = DEFAULT_CONFIG.copy()
    if filename:
        if not os.path.isfile(filename):
            raise ConfigError, 'No such configuration file %s' % filename
        parser = ConfigParser()
        parser.parse(filename)
        options = parser.getOptions()
        config.update(options)
        sections = parser.getSections()
        sitelist = []
        for section in sections:
            if section.getType() == 'site':
                sitelist.append((section['priority'], section['location'], section['regexp']))
        if sitelist:
            config["sites"] = sitelist
    return config




