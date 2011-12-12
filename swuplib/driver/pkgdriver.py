# $Id: pkgdriver.py,v 1.30 2004/11/30 14:15:40 christht Exp $
#  Copyright 2003 - 2004 Tor Hveem - <tor@bash.no>

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

#
# This is the interface all drivers must uphold, as it's what swup and rdfgen
# uses. Any new driver must implement these methods and return the correct
# values as described below.
#
import types
from swuplib import ex

class pkgdriver:

    def __init__(self, config, log=None):
        ''' Takes config and log, reads drivername from config and imports the
        correct package driver. '''
        self.log = log
        drivername = config["driver"]
        try:
            exec "from swuplib.driver import %s; self.driver = %s.driver(config,log)" %\
                 (drivername, drivername)
        except ImportError:
            message = "Unable to load driver for packaging system."
            self.log.write_stderr(message)
            self.log.write_syslog_err(message)
            raise ex.upgrade_error, message
        except:
            raise
        try:
            self.driver.prime()
        except:
            message = "Unable to access the package manager database."
            self.log.write_stderr(message)
            self.log.write_syslog_err(message)
            raise ex.driver_error, message

    def check_package_conflict(self, package1, package2):
        ''' Returns True if conflicts are found. '''
        self._check_input(package1, types.DictType)
        self._check_input(package2, types.DictType)
        return self.driver.check_package_conflict(package1, package2)
        
    def get_conflicts(self, package):
        ''' Returns a list of installed package dicts which the given package
        conflicts against. '''
        self._check_input(package, types.DictType)
        return self.driver.get_conflicts(package)

    def get_conflictors(self, package):
        ''' Returns a list of installed package dicts which conflicts with 
        the given package. '''
        self._check_input(package, types.DictType)
        return self.driver.get_conflictors(package)
        
    def get_installed(self):
        ''' Returns all installed packages '''
        return self.driver.get_installed()
        
    def get_db_latest(self):
        ''' Returns a latest-like dictionary of the installed packages '''
        return self.driver.get_db_latest()
        
    def get_package(self, name, file=False):
        ''' Parses the local file or database and return a package dictionary.
        The format of the dictionary is the same as the spi-parser creates, and
        is vital for the rest of swup.
        If file is given, treat name as file '''
        self._check_input(name, types.StringTypes)
        return self.driver.get_package(name, file)
    
    def get_packages(self, name):
        ''' Parses the local database and return a list of package 
            dictionaries. If none is found the list will be empty. '''
        self._check_input(name, types.StringTypes)
        return self.driver.get_packages(name)

    def get_providers(self, resourcename, operator="", version="", release=""):
        ''' Returns two lists of package dictonaries, on of packages that both
            provides the given resource and doing so at a valid level, and one
            that provides the given resource, but does not suffice on version. 
            '''
        self._check_input(resourcename, types.StringTypes)
        self._check_input(operator, types.StringTypes)
        self._check_input(version, types.StringTypes)
        self._check_input(release, types.StringTypes)
        return self.driver.get_providers(resourcename,operator,version,release)

    def get_requires(self, packagename):
        ''' Returns a list of package names that are installed locally and 
            requires one or more of the resources the given package provides.
            Returns empty list if given package is not installed.'''
        self._check_input(packagename, types.StringTypes)
        return self.driver.get_requires(packagename)
        
    def install(self, transactiondata):
        ''' Installs/upgrades packages, given transactiondata. The 
        transactiondata contains information about which packages should be
        installed together, and where the packages, and signatures are 
        available for download.'''
        #
        #
        # This is some times a DictType, and I don't feel like fixing it
        # right now.
        #self._check_input(transactiondata, types.InstanceType
        try:
            return self.driver.install(transactiondata)
        except:
            raise

    def erase(self, packagenames):
        ''' Erases packages, given a list with package name(s) ''' 
        self._check_input(packagenames, types.ListType)
        try:
            return self.driver.erase(packagenames)
        except: 
            raise 

    def is_installed(self, package):
        ''' Accepts a package dictionary or a package name.
            Returns -2 if the package is not installed
            Returns -1 if the package is installed and >  package dict
            Returns  0 if the package is installed and == package dict
            Returns  1 if the package is installed and <  package dict
            Returns  2 if the package is only installed (no dict given)'''
        try:
            self._check_input(package, types.DictType)
        except ex.input_error:
            self._check_input(package, types.StringTypes)
        return self.driver.is_installed(package)

    def opendb_readwrite(self):
        ''' Make sure the database is ready to be written to. Only needed for
        old versions of rpm, but does nothing bad. '''
        return self.driver.opendb_readwrite()
    
    def remove(self, transactiondata):
        ''' Removes packages, given transactiondata. 
        transactiondata contains information about which packages should be
        removed together.'''
        self._check_input(transactiondata, types.DictType)
        return self.driver.remove(transactiondata)

    def version_compare(self, package1, package2):
        ''' Compares the version of two packages.
            Returns  1 if package1 >  package2
            Returns  0 if package1 == package2
            Returns -1 if package1 <  package2 '''
        self._check_input(package1, types.DictType)
        self._check_input(package2, types.DictType)
        return self.driver.version_compare(package1, package2)

    def system_version(self):
        return self.driver.system_version()
        
    def _check_input(self, input, pythontype):
        ''' Check if input is of the given type. '''
        if type(input) is pythontype:
            return True
        elif pythontype == types.StringTypes and type(input) in pythontype:
            return True
        else:
            raise ex.input_error, "Invalid type"
