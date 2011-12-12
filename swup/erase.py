# -*- python -*-
# vim: set tabstop=4 expandtab shiftwidth=4

#  Copyright 2004 Tor Hveem - <tor@bash.no>
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
import upgrade, string
from upgrade import Upgrade
               
DEBUG=False

class EraseObject:

    def __init__(self, pkgdrv, log, packages):
        self.pkgdrv = pkgdrv
        self.log = log
        self.resolved = []
        self.unresolved = []
        self.populate(packages)
    
    def get_next_unresolved(self):
        if len(self.unresolved) > 0:
            return self.unresolved.pop(0)

    def is_unresolved(self, package):
        if package in self.unresolved: 
            return True

    def is_resolved(self,package):
        if package in self.resolved: 
            return True
    
    def get_resolved(self):
        return self.resolved

    def populate(self, packages):
        for package in packages:
            #Check if package is installed
            if self.pkgdrv.is_installed(package) == -2:
                self.log.write_tty('\rSkipping %s, not installed.' \
                        %package+(70-len(package))*' ')
            else:
                self.unresolved.append(package)

    def set_resolved(self, package):
        if package not in self.resolved:
            self.resolved.append(package)
        if package in self.unresolved:
            self.unresolved.remove(package)
    

class Erase(Upgrade):

    def __init__(self, packagenames, configdict=None):
        Upgrade.__init__(self,configdict)
        self.pkgdrv.opendb_readwrite()
        self.eraseobj = EraseObject(self.pkgdrv, self.log,packagenames)

    def _resolve(self):
        ''' Resolved packages that need to be removed. '''
        package = self.eraseobj.get_next_unresolved()
        while(package):
            self.eraseobj.set_resolved(package)
            self.log.write_tty("\rResolving: %s" %package+(69-len(package))*' ')
            requiredby = self.pkgdrv.get_requires(package)
            if len(requiredby) == 0:
                    if self.eraseobj.is_unresolved(package) and \
                            not self.eraseobj.is_resolved(package): 
                        self.eraseobj.set_resolved(package)
            for requires in requiredby:
                if requires == package: continue
                if self.eraseobj.is_resolved(requires): continue
                if not self.eraseobj.is_unresolved(requires): 
                    self.eraseobj.unresolved.append(requires)
            
            package = self.eraseobj.get_next_unresolved()
        
        return self.eraseobj.get_resolved()
        

    def main(self):
        self.resolved = self._resolve()
        if len(self.resolved) > 0:
            msg = ""
            unremovable = False
            index = 0
            for package in self.resolved:
               if package in self.config['unremovable']:
                   if not string.lower(str(self.config['force'])) == "yes":
                       unremovable = True
               msg += package+'\n'
               index += 1
            message = "\rThe following package(s) will be removed:\n"
            if unremovable:
                message = "\rOrdinary removal of the following package(s) "
                message += "is not allowed:\n"
                for upkg in self.config['unremovable']:
                    message += "%s\n" %upkg
                message += "Use option --force to force removal of this set:\n"
                message += msg
            else:
                message = "\rThe following package(s) will be removed:\n"
                message += msg
            self.log.write_stdout(message)
            message = ""
            message += "A total of %s package(s) scheduled for removal." %index
            self.log.write_stdout(message)
            if string.lower(str(self.config["poll_only"])) == "yes":
                message = "Option poll-only enabled, will not remove."
                self.log.write_stdout(message)
            elif unremovable and \
                    not string.lower(str(self.config["force"])) == "yes":
                pass
            else:
                self.pkgdrv.erase(self.resolved)
        else:
            self.log.write_stderr('\rNo packages to remove.\n')

