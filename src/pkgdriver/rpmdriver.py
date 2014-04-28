# $Id: rpmdriver.py,v 1.8 2001/06/18 13:08:39 olafb Exp $

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

import os, rpm, sys, types, utils

# exceptions
install_error = "rpmdriver.install_error"
query_error = "rpmdriver.query_error"
general_error = (install_error, query_error)

# useful constants
true, false = 1, 0

DEBUG = true
LOG_MODETEXT = {"upgrade": "Upgraded",
                "install": "Installed" }
TTY_MODETEXT = {"upgrade": "Upgrading",
                "install": "Installing"}


def flag2str(flag):
    retstr = ""
    if flag & rpm.RPMSENSE_LESS :
	retstr = retstr + "<"
    if flag & rpm.RPMSENSE_GREATER :
	retstr = retstr + ">"
    if flag & rpm.RPMSENSE_EQUAL :
	retstr = retstr + "="
    return retstr



class driver:
    install_error = "rpmdriver.install_error"
    query_error = "rpmdriver.query_error"
    general_error = (install_error, query_error)

    def __init__(self, log):
        self.fd = 0
        self.db = None
        self.conflicts = None
        self.packages = None
        self.log = log

        
    def __del__(self):
        if self.db:
            del self.db
        if self.fd != 0:
            os.close(self.fd)
    
    def _install_callback(self, what, bytes, total, h, user):

        if what == rpm.RPMCALLBACK_INST_OPEN_FILE:
            filename = self.filenames[h[rpm.RPMTAG_NAME]]
            mode = self.modes[h[rpm.RPMTAG_NAME]]

            tty_mode =  TTY_MODETEXT[mode]
            self.log.write_tty( "\r"+ " "*80 )
            message = "\r%s %s - " % (tty_mode, os.path.basename(filename))
            self.log.write_tty( message )
            self.fd = os.open(filename, os.O_RDONLY)
            return self.fd

        elif what == rpm.RPMCALLBACK_INST_CLOSE_FILE:
            filename = self.filenames[h[rpm.RPMTAG_NAME]]
            mode = self.modes[h[rpm.RPMTAG_NAME]]

            tty_mode = TTY_MODETEXT[mode]
            message = "\r%s %s - done\n" % \
                      (tty_mode, os.path.basename(filename))
            self.log.write_tty( message )

            log_mode =  LOG_MODETEXT[mode]
            message = "%s %s." % (log_mode, os.path.basename(filename))
            self.log.write_log( message )

            if not self.log.isatty_stdout:
                self.log.write_stdout( message )
                
            os.close(self.fd)
            self.fd = 0


    def install(self, transaction):
        'Install rpm packages given a dictionary of packages.'

        # Check that all packages are available.
        if (len(transaction) < 1) or not transaction:
            raise self.install_error, "unrecogniced transaction format."
        missingfiles = []
        for package in transaction.values():
            if not os.path.isfile(package.localfilename):
                missingfiles.append(package.localfilename)
        if len(missingfiles) > 0:
            raise self.install_error, "can not find files '%s'" % \
                  missingfiles

        # Create a rpm-transaction and check for dependencies.
        try:
            self.open_db(writeflag=true)
        except rpm.error, errmsg:
            raise self.install_error, errmsg
            
        ts = rpm.TransactionSet('/', self.db)
        self.filenames = {}
        self.modes = {}
        ts_names = ""

        for package in transaction.values():
            if package.flag == "upgrade":
                transactionmode = "u"
            elif package.flag == "install":
                transactionmode = "i"
            else:
                raise self.install_error, \
                      "mode '%s' for package '%s' not recognized." \
                      % (package.flag, package.name)
            fd = os.open(package.localfilename, os.O_RDONLY)
            hdr = rpm.headerFromPackage(fd)[0]
            self.filenames[hdr[rpm.RPMTAG_NAME]] = package.localfilename
            self.modes[hdr[rpm.RPMTAG_NAME]] = package.flag
            os.close(fd)
            ts.add(hdr, hdr, transactionmode)
            if ts_names == "":
                ts_names = package.name
            else:
                ts_names = ts_names + " " + package.name 

        # Check dependencies (If there are any dependencies, there must be
        # something wrong with the SPI-files).
        ts.order()
        deps = ts.depcheck()
        if deps:
            deps_message = ""
            for ((name, version, release), (reqname, reqversion),
                 flags, suggest, sense) in deps:
                if sense == rpm.RPMDEP_SENSE_REQUIRES:
                    if reqversion == "":
                        deps_message = deps_message + \
                            "\tPackage '%s' requires '%s'.\n" % \
                            (name, reqname)
                    else:
                        deps_message = deps_message + \
                            "\tPackage '%s' requires '%s' version '%s'.\n"% \
                            (name, reqname, reqversion)
            raise self.install_error, \
                  "Unable to resolve dependencies for the packages"\
                  "\n\t%s\n%s" % (ts_names, deps_message)

        # Install the rpms
        errors = ts.run(0, 0, self._install_callback, '')
        self.log.write_tty( '\n' )
        if errors:
            error_description = "RPM: "
            for error in errors:
                error_description = error_description + str(error[0]) + "\n"
            error_description = error_description + "Skipping: %s." %\
                                ts_names
            raise self.install_error, error_description


    def open_db(self, writeflag=false):
        """(Re)opens the packagedatabase. Optional argument writeflag can
        be set to 1 if database should be (re)opened in write-mode.
        Default is 0 (read only) for the database."""
        try:
            self.db = rpm.opendb(writeflag,'/')
        except rpm.error:
            raise self.query_error, "unable to open local rpm database."


    def query(self, resource):
        "Query packaging system for installed resource."
        self.open_db()

        # Had to add this try/except hack, because rpm 4 raises rpm.error
        # when <string> in findbyname(<string>) does not match. Shame on rpm.
        try:
            # Check for package first.
            index = self.db.findbyname(resource)
            # If there was no matching package, check for capability.
            if len(index) < 1:
                index = self.db.findbyprovides(resource)
                
            # Last, check for file.
            if len(index) < 1:
                index = self.db.findbyfile(resource)
            if len(index) < 1:
                return None
            retval = []
            for i in index:
                header = self.db[i]
                retval.append([header[rpm.RPMTAG_NAME],
                               header[rpm.RPMTAG_VERSION],
                               header[rpm.RPMTAG_RELEASE]])
            return retval
        except rpm.error, message:
            return query_error, message


    def get_installed_pkgs(self):
        """Query packaging system for all installed packages.
        Returns a dictionary with package name as key and a the tuple
        ((<version>, <release>, <group>), ...) as value."""
        if not self.packages:
            self._generate_installed()
        return self.packages


    def query_by_name( self, name ):
        if not self.packages:
            self._generate_installed()
            if self.packages.has_key( name):
                return self.packages[name]
            else:
                return None
            

    def _generate_installed( self ):
        self.open_db()
        pkgdata = {}
        conflictdata = {}
        key = self.db.firstkey()
        while key:
            hdr = self.db[key]
            name = hdr[rpm.RPMTAG_NAME]

            if hdr[rpm.RPMTAG_CONFLICTNAME]:
                conflictnames = hdr[rpm.RPMTAG_CONFLICTNAME]
                conflictversions = hdr[rpm.RPMTAG_CONFLICTVERSION]
                conflictflags = hdr[rpm.RPMTAG_CONFLICTFLAGS]
                if len(conflictnames) == 1:
                    conflictname = conflictnames[0]
                    if not conflictdata.has_key( conflictname ):
                        conflictdata[conflictname] = []
                    conflictdata[conflictname].append((
                         ( (flag2str(conflictflags), conflictversions[0]),
                           name )
                        ))
                else:
                    for i in range( len(conflictnames) ):
                        conflictname = conflictnames[i]
                        if conflictdata.has_key( conflictname ):
                            if conflictflags:
                                conflictdata[conflictname].append(
                                               ((flag2str(conflictflags[i]),
                                               conflictversions[i]), name ))
                            else:
                                conflictdata[conflictname].append(
                                    ( (None, None), name )
                                    )
                    
            if not pkgdata.has_key( name ): pkgdata[name] = []
            pkgdata[name].append((
                hdr[rpm.RPMTAG_VERSION],
                hdr[rpm.RPMTAG_RELEASE],
                hdr[rpm.RPMTAG_GROUP]))
            key = self.db.nextkey(key)

        self.conflicts = conflictdata
        self.packages = pkgdata

        
    def check_for_conflict( self, name, version ):
        if not self.conflicts:
            self._generate_installed()

        conflict_packagenames = []
        # Is there a conflict for package named <name> at all?
        if not name in self.conflicts.keys():
            return conflict_packagenames

        # There is one or more conflicts, check them.
        for conflict in self.conflicts[name]:
            ((flag, conflict_version), conflict_package) = conflict
            if not flag:
                conflict_packagenames.append(conflict_package)
                continue

            comp = utils.version_cmp( (version, ""), (conflict_version, "") )
            flag = map( None, flag )

            if (comp < 0) and ("<" in flag):
                conflict_packagenames.append(conflict_package)
                continue

            if (comp == 0) and ("=" in flag):
                conflict_packagenames.append(conflict_package)
                continue

            if (comp > 0) and (">" in flag):
                conflict_packagenames.append(conflict_package)
                continue
            
        return conflict_packagenames





















