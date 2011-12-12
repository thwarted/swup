# $Id: config.py,v 1.37 2005/07/20 12:21:03 christht Exp $
"""Module contains main function 'parse(filename=None)' for parsing
config for swup. Function returns a dictionary of config variables. If
a valid optional filename is given, variables defined in file will
override the corresponding default variables.
"""

#  Copyright 2001 - 2003 Trustix AS - <http://www.trustix.com>
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


import shlex, os, string, sys
from swuplib import log
from swuplib import ex
import types
import re

tell = 1

# defaults
DEFAULT_CONFIG_FILE = "/etc/swup/swup.conf"
DEFAULT_CONFIG = {
"driver": "rpmdriver",
"root": "/",
"stage": None,
"prog_total": 0,
"resolved": "resolved.pickle",
"gnupgdir": "/etc/swup/gnupg",
"cachedir": "/var/cache/swup",
"tmpdir": "/var/spool/swup",
"keyring": "",
"unremovable": ['swup'],
"interactive_logged": "yes",
"download_only": "no",
"download_first": "no",
"save_to":  "",
"poll_only": "no",
"sites": None,
"local_first": "no",
"auto_reboot": "no",
"force": "no",
"reboot_delay": 5,
"flush_installed": "yes",
"exclude_pkg_regexp": "",
"include_pkg_regexp": ".*",
"include_conf": "conf.d/*.conf",
}

class ConfigSection:
    def __init__(self, type, log):
        self.type = type
        self.log = log
        self.options = {}

    def __str__(self):
        return str(self.options)

    def set(self, option, value):
        #function to set sub-option/value in a section.
        #option "priority" renamed as "class" handle it accordingly
        #for old users still using priority using this IF block
        if option == "priority":    #option priority renamed as class
            new = "class"
            errmsg = ex.deprecated_option_error ( option ,new)
            self.log.write_syslog_warning( "%s" %errmsg )
            if tell == 1:
                self.log.write_stdout( errmsg, True )    
                #syntax: write_stdout( message, newline )
            option = new    #replace priority with class option.
                    
        if option in ["class"]:
            self.options[option] = int(value)
        elif option in ["regexp", "location", "name"]:
            self.options[option] = str(value)
        elif option == "enabled":
            try:
                value = int(value)
            except ValueError:
                pass
            if value == "yes" or value == 1:
                self.options[option] = True
            elif value == "no" or value == 0:
                self.options[option] = False
            else:
                raise ex.bad_value_error, (option, value)
        else:
            raise ex.bad_option_error, option

    def getType(self):
        return self.type

    def validate(self):
        """This function makes sure that all required options are set for the section."""
        keys = self.options.keys()
        if not 'location' in keys:
            raise ex.missing_option_error, "Missing URL for site."
        if not 'name' in keys:
            self.set("name", "")
        if not 'regexp' in keys:
            self.set("regexp", ".*")
        if not 'class' in keys:
            self.set("class", 0)
        if not 'enabled' in keys:
            self.set("enabled", 1)
            
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
    def __init__( self , tell, log ):
        "Set up configuration and run initialization functions."
        self.log = log
        self.options = {}
        self.sections = []
        self.tell = tell

    def stripQuotes(self, text):
        if len(text) > 1:
            if text[0] == '"' and text[-1] == '"' \
               or text[0] == "'" and text[-1] == "'":
                return text[1:-1]
        return text
    
    
    def addOption(self, option, value):
        # Check for deprecated options:
        error = 0
        removed_options = [ "passwd_file", 
                            "logfile", 
                            "flush_cache", 
                            "exclude_group_regexp",
                            "include_group_regexp"]
        for opt in removed_options:
            if option == opt:
                errmsg = ex.option_removed_error(option)
                self.log.write_syslog_warning( "%s" %errmsg )
                if self.tell == 1:
                    self.log.write_stderr( "Warning: %s" %errmsg, True )
                error = 1
        if not error == 0:
                return


        # Validate type and possibly raise exception if
        # the option is unknown.
        elif option not in DEFAULT_CONFIG.keys(): #check with available options
            raise ex.bad_option_error, option
        else:
            self.options[option] = self.stripQuotes(value)    
            #set the option dict as a key/value pair (token = value)
    
    
    def parse(self, filename):
        try:
            fd = open(filename)
        except IOError:
            raise ex.io_error, "Unable to open '%s' for reading" %filename
        except:
            raise
        config = shlex.shlex(fd)
        finished = 0
        state = '-'
        #
        #state flag:  used to parse through the configuration.
        #state = "-" : (Initialized state) Look for options or sections.
        #state = "O" : Next token should be "=" (assignment) or "{" (section).
        #state = "=" : Found direct option next token should be value.
        #state = "{" : Found section next token should be section params.
        #state = "{O": Found section suboption next token "=" (assignment).
        #state = "{=": Found "=" (assignment) look for sub-value in next token.
        #
        option = None
        section = None
        #iterate through the tokens to parse configuration options
        while not finished:
            token = config.get_token() #use shlex to take first config option(token)
            #comments are ignored by shlex.
            if token == "":    #config file is empty
                finished = 1    #set finished flag to exit parser loop
            else:
                if state == '-': #'-' signifies option
                    # reading option name
                    option = token
                    state = 'O'
                    #set state to parse values either '= (option)' or '{} (section)'
                    #to parse in the next iteration.
                elif state == 'O':
                    # next token should be '=' for assignment, or
                    # '{' to start a section
                    if token == '=':
                        state = '=' #check value in next iteration.
                    elif token == '{':    #check  in the next iteration.
                        if option != "site": 
                            #only site is allowed as as a section for now
                            raise ex.config_parse_error(filename, config, 
                                        "Unrecognized section " + option)
                        state = '{'  #check section options in next iteration
                        section = ConfigSection(option, self.log)
                    else:
                        raise ex.config_parse_error(filename, config, 
                                        "Expecting '=' or '{'")

                elif state == '=':
                    # next token is the value of the option
                    try:
                        self.addOption( option, token )
                        option = None
                    except ex.bad_option_error, errmsg:
                        raise ex.config_parse_error(filename, config, str(errmsg))
                    except:
                        raise
                    state = '-'
                
                elif state == '{':
                    if token == '}':
                        try:
                            section.validate()
                            self.sections.append(section)
                            section = None
                        except ex.missing_option_error, e:
                            raise ex.config_parse_error(filename, config, ex.__str__())
                        except:
                            raise
                        state = '-'
                    else:
                        option = token
                        state = '{O' #option is a sub-option in a section

                elif state == '{O':
                    # next token should be '=' for assignment
                    if token == '=':
                        state = '{=' #value for sub-option inside section
                    else:
                        raise ex.config_parse_error(filename, config, 
                                    "Expecting '='")

                elif state == '{=':
                    # next token is the value of the option
                    try:
                        section.set(option, self.stripQuotes(token))
                        #^set sub option/value for the section.
                    except ex.bad_option_error, errmsg:
                        raise ex.config_parse_error(filename, config, str(errmsg))
                    except:
                        raise
                    option = None
                    state = '{'
        fd.close()
        
    def getSections(self):
        return self.sections

    def getOptions(self):
        return self.options

def include_conf(filename, config, parser):
    options = parser.getOptions()
    if not 'include_conf' in options.keys():
        include_conf_line = config['include_conf']
    else:
        include_conf_line = options['include_conf']
    
    import glob
   
    confs = []
    if os.path.isabs(include_conf_line):
        to_glob = include_conf_line
    else:
        to_glob = os.path.join(os.path.dirname(filename), include_conf_line)
      
    confs = glob.glob(to_glob)
    for conf in confs:
        parser.parse(conf)

    # Stolen from yum
def get_arch():
    arch = os.uname()[4]
    newarch = None
    if re.search('86', arch):
        newarch = 'i586'
    if re.search('sparc', arch) or re.search('sun', arch):
        newarch = 'sparc'
    if re.search('sparc64', arch) or re.search('sun64', arch):
        newarch = 'sparc64'
    if re.search('alpha', arch):
        newarch = 'alpha'
    if re.search('ppc', arch):
        newarch = 'ppc'
    if re.search('ppc64', arch):
        newarch = 'ppc64'
    if re.search('x86_64', arch):
        newarch = 'x86_64'
    if not newarch:
        newarch = arch
    return newarch

def do_replace(string, config, logger):
    if string is None:
        return string

    basearch_reg = re.compile('\$basearch')
    releasever_reg = re.compile('\$releasever')

    # test if we need the pkgdriver:
    count = basearch_reg.findall(string)
    count.extend(releasever_reg.findall(string))
    if count:
        from swuplib.driver import pkgdriver
        driver = pkgdriver.pkgdriver(config, logger)
        (string, count) = basearch_reg.subn(get_arch(), string)
        (string, count) = releasever_reg.subn(driver.system_version(), string)
        
    return string

def replace_vars(config, logger):
    pass
    for key in config.keys():
        if type(config[key]) in types.StringTypes:
            config[key] = do_replace(config[key], config, logger)    

        if key == "sites" and type(config[key]) is types.ListType:
            replaced_sites = []
            for site in config[key]:
                (cl, location, regexp, name, enabled) = site
                location = do_replace(location, config, logger)
                name = do_replace(name, config, logger)
                replaced_sites.append((cl, location, regexp, name, enabled))
            config[key] = replaced_sites

def parse(filename=None, silent=None, full=True):
    logger = None
    if silent == 1:
        tell = 0
    else:
        tell = 1

    config = DEFAULT_CONFIG.copy()
    import os
    config['listsdir'] = os.path.join(config['cachedir'], 'lists')
    config['md5sumfile'] = os.path.join(config['cachedir'], 'md5sums')
    if not filename:
        filename = DEFAULT_CONFIG_FILE
    if filename:
        if not os.path.isfile(filename):
            if not silent:
                message = "No config file found, using default configuration.\n"
                sys.stderr.write(message)
            return config
        logger = log.log(log.LOGLEVEL_NORMAL, True )
        parser = ConfigParser( tell, logger )
        parser.parse(filename)
        include_conf(filename, config, parser)
        options = parser.getOptions()
        config.update(options)
        sections = parser.getSections()
        sitelist = []
        for section in sections:
            if section.getType() == 'site':
                sitelist.append((section['class'], section['location'], section['regexp'], section['name'], section['enabled']))
        if sitelist:
            nulls = 0
            for site in sitelist:
                (pri, url, regexp, name, enabled) = site
                if enabled and pri == 0:
                    nulls += 1
            if nulls == 0:
                raise ex.no_null_class_found_error, \
                    "Error: No site configured with 'class = 0' found."
            elif nulls == 1:
                errmsg = "Only one site configured with 'class = 0' found."
                sys.stderr.write( "Warning: %s\n" %errmsg)
            config["sites"] = sitelist

    # check uid != 0
    if os.getuid() != 0:
        cachedir = os.path.join(os.path.expanduser("~"), '.swup/cache')
        tmpdir = os.path.join(os.path.expanduser("~"), '.swup/tmp')
        gnupgdir = os.path.join(os.path.expanduser("~"), '.swup/gnupg')
        if not os.path.isdir(gnupgdir):
            os.makedirs(gnupgdir)
        userfile = os.path.join(gnupgdir,'pubring.gpg')
        rootfile = os.path.join(config['gnupgdir'],'pubring.gpg')
        config['keyring'] = rootfile
        if not os.path.isfile(userfile) and os.path.isfile(rootfile):
            import shutil
            try:
                shutil.copyfile(rootfile, userfile)
            except IOError:
                pass
        config['cachedir'] = cachedir
        config['tmpdir'] = tmpdir
        config['gnupgdir'] = gnupgdir

    # set up listsdir and md5sumfile
    config['listsdir'] = os.path.join(config['cachedir'], 'lists')
    config['md5sumfile'] = os.path.join(config['cachedir'], 'md5sums')

    if not logger:
        logger = log.log(log.LOGLEVEL_NORMAL, True )
    if full:
        replace_vars(config, logger)
    return config




