#  Copyright 2004 Comodo Trustix Ltd - <http://www.trustix.com>
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



"""General:"""
class swup_error(Exception):
    def __init__(self, value1=None, value2=None, value3=None, value4=None):
        self.value1 = value1
        self.value2 = value2
        self.value3 = value3
        self.value4 = value4
    def __str__(self):
        result = ""
        if self.value1:
            result += "%s\n" %self.value1
        if self.value2:
            result += "%s\n" %self.value2
        if self.value3:
            result += "%s\n" %self.value3
        if self.value4:
            result += "%s\n" %self.value4
        return str(result)

class coder_messed_up_error(swup_error): pass
class parse_error(swup_error): pass
class io_error(swup_error): pass

"""swup.py:"""
class cmdline_error(swup_error): pass
class setup_error(swup_error): pass

"""cmdline.py"""
class cmdline_unknown_error(swup_error): pass
class wrong_number_of_args_error(swup_error): pass
class too_many_operations_error(swup_error): pass
class too_few_operations_error(swup_error): pass

"""gpg.py:"""
class import_key_error(swup_error): pass
class delete_key_error(swup_error): pass
class list_keys_error(swup_error): pass
class signature_error(swup_error): 
    
    def __str__(self):
        import os
        filename = os.path.basename(self.value1)[:-4]
        return "The PGP signature of "+filename+" could not be verified, possible issues are:\n"+\
"- The PGP key which this file is signed by, is not yet imported into swup.\n"+\
"- The systems clock is set horribly wrong.\n"+\
"- The file, or its signature file, was damaged during download.\n"+\
"- The file was not signed at all.\n"+\
"In any case, this file will not be trusted.\n"

"""rdfgen.py:"""
class format_error(swup_error): pass
class duplicate_error(swup_error): pass

"""download.py:"""
class download_error(swup_error): pass
class auth_error(swup_error): pass

"""resolver.py:"""
class resolve_error(swup_error): pass
class filter_exclude_error(swup_error): pass
class empty_package_list_error(swup_error): pass

"""upgrade.py:"""
#class upgrade_error(swup_error): pass

"""pkgdriver.py / rpmdriver.py:"""
class driver_error(swup_error): pass
class install_error(swup_error): pass
class upgrade_error(swup_error): pass
class erase_error(swup_error): pass
class input_error(swup_error): pass
class query_error(swup_error): pass

class not_installed_error(swup_error):
    def __str__(self):
        return "The given package '%s' is not installed.\n" %self.value1

class unmet_local_deps_error(swup_error):
    def __str__(self):
        return "Unable to upgrade package set due to unmet local dependencies."
    def details(self):
        result = str(self)
        result += "\n\t%s\n%s\n" % (self.value1, self.value2)
        result += "Possible reasons:\n"
        result += "- A locally installed package depends on the old version "
        result += "of one of the \n  packages we tried to upgrade.\n"
        result += "- The remote repository is corrupt.\n"
        result += "Possible solutions:\n"
        result += "- Run swup with --local-first option several times.\n"
        result += "- Report the problem to your vendor."
        return result



"""config.py:"""
class no_null_class_found_error(swup_error): pass
class missing_option_error(swup_error): pass

class config_parse_error(swup_error):
    def __str__(self):
        msg = 'Error in ' + self.value1 + ', line ' + str(self.value2.lineno)
        if self.value2.token != "":
            msg = msg + " near '" + self.value2.token + "'"
        msg = msg + ": " + self.value3
        return msg

class bad_option_error(swup_error):
    def __str__(self):
        return 'Unrecognized option ' + self.value1

class bad_value_error(swup_error):
    def __str__(self):
        return "Bad value '" + str(self.value2) + "' for option " + self.value1

class deprecated_option_error(swup_error):
    def __str__(self):
        return "Deprecated option '" + self.value1 \
                + "' should be replaced by '" \
                + self.value2 + "'."

class option_removed_error(swup_error):
    def __str__(self):
        return "Deprecated option '" \
                + self.value1 + "' ignored."


"""spiparser.py"""
class spi_parse_error(swup_error):
    def __str__(self):
        return "Unable to parse file '%s'" %self.value1
