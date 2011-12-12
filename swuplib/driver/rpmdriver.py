# $Id: rpmdriver.py,v 1.128 2005/07/12 11:09:14 christht Exp $

#  Copyright 2001 Trustix As - <http://www.trustix.com>
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

import os, rpm, sys, types, string, re, time 
from swuplib import utils
from swuplib import ex
DEBUG = False

LOG_MODETEXT = {"upgrade": "Upgraded",
                "install": "Installed" }
TTY_MODETEXT = {"upgrade": "Upgrading",
                "install": "Installing"}

class driver:
    def __init__(self,config,log=None):
        self.config = config
        self.root = self.config['root']
        self.log = log
        self.fd = 0
        #self.conflicts = None
        self.packages = {}
        self.latest = {}
        self.cb_limit = 2
        self.cb_count = 0
    
    def prime(self):
        try:
            uid = os.getuid()
            if 'ts' in dir(rpm):
                # FIXME: make sure it works for users too.
                #This means we are in RPM>4.1 mode
                self.oldrpm = False
                self.db = rpm.TransactionSet(self.root)
                self.db.setVSFlags(~(rpm.RPMVSF_NODSA|rpm.RPMVSF_NORSA))
            else:
                self.oldrpm = True
                self.db = rpm.opendb(False, self.root)
        except rpm.error:
            raise ex.query_error, "unable to open local rpm database."

    def check_package_conflict(self, package1, package2):
        if package1["conflicts"]:
            for conflict in package1["conflicts"]:
                if not conflict: continue
                if conflict["name"] == package2["name"]:
                    if not conflict["flag"]:
                        return True 
                    return self._check_conflict_versions(package2, 
                                        conflict["flag"], conflict)

        if package2["conflicts"]:
            for conflict in package2["conflicts"]:
                if not conflict: continue
                if conflict["name"] == package1["name"]:
                    if not conflict["flag"]:
                        return True 
                    return self._check_conflict_versions(package1, 
                                        conflict["flag"],  conflict)


    def get_conflictors(self, package):
        self._generate_installed()
        name = package["name"]
        real_conflictors = []

        # There is one or more conflicts, check them.
        if self.conflictors.has_key(name):
            for dict in self.conflictors[name]:
                # compare versions using flag: XXX
                if self._check_conflict_versions(dict, dict['flag'], package):
                    continue
                else: 
                    real_conflictors.append(dict)
            
            return real_conflictors
        
    def get_conflicts(self, package):
        conflicts = []
        packageconflicts = package['conflicts']
        for conflict in packageconflicts:
            conflictname = conflict['name']
            
            if self.is_installed(conflictname) == -2: continue
            installedconflict = self.get_package(conflictname)
            # Check if that version is conflicted
            if not conflict['flag']: 
                conflicts.append(installedconflict)
            else:
                if self._check_conflict_versions(installedconflict, 
                                        conflict['flag'], conflict):
                    conflicts.append(installedconflict)

        return conflicts
            
    def get_installed(self):
        self._generate_installed()
        return self.packages

    def get_db_latest(self):
        self._generate_db_latest()
        return self.latest

    def get_package(self, name, file=False):
        '''Takes a filename for a rpm-package. Returns a package dictionary.'''
        dict = {}
        if file:
            file_output = os.popen("file %s" % name).read()
            file_output = string.split(file_output)
            dict["md5sum"] = utils.md5sum(name)
            package_type, package_type_version = file_output[1:3]
            fd = os.open(name, os.O_RDONLY)
            dict["filename"] = name
            dict["basename"] = os.path.basename(name)
            if self.oldrpm:
                rpmheader = rpm.headerFromPackage(fd)[0]
            else:
                #RPM>=4.1 needs this
                ts = rpm.TransactionSet(self.root)
                ts.setVSFlags(~(rpm.RPMVSF_NOMD5|rpm.RPMVSF_NEEDPAYLOAD|rpm._RPMVSF_NOSIGNATURES|rpm._RPMVSF_NODIGESTS))
                ts.setVSFlags(~(rpm.RPMVSF_NODSA|rpm.RPMVSF_NORSA))
                rpmheader = ts.hdrFromFdno(fd)
            os.close(fd)
            dict["package_type"] = (package_type + package_type_version)
        else:
            #If self.packages has been generated, we could just return the 
            #dict already generated.
            if self.packages.has_key(name):
                return self.packages[name]
            if self.oldrpm:
                packagelist = self.db.findbyname(name)
                if not len(packagelist) > 0:
                    return None
                index = self.db.findbyname(name)[0]
                rpmheader = self.db[index] 
            else:
                #RPM>=4.1 needs this
                headers = self.db.dbMatch('name',str(name))
                rpmheader = None
                if headers.count() == 0: 
                    return None
                else:
		    for header in headers:
		        rpmheader = header
        dict.update(self._create_package(rpmheader))
        return dict

    def get_packages(self, name):
        '''Takes a package name. Returns a list of package dictionaries.'''
        dict = {}
        packageheaders = []
        packages = []
        if self.oldrpm:
            packageindexes = self.db.findbyname(name)
            for index in packageindexes:
                packageheaders.append(self.db[index])
        else:
            #RPM>=4.1 needs this
            headers = self.db.dbMatch('name',str(name))
            for rpmheader in headers:
                packageheaders.append(rpmheader)

        for rpmheader in packageheaders:
            packages.append(self._create_package(rpmheader))

        return packages

    def get_providers(self, resource, operator, version, release):
        valids = []
        invalids = []
        foundheaders = []
        checkver = True

        unwantedrequires = self._rpmlib_hack()
        for req in unwantedrequires:
            if resource == req:
                valids.append(self.get_package('rpm'))
                return valids, invalids
        if not operator or not version:
            checkver = False

        # Had to add this try/except hack, because rpm 4 raises rpm.error
        # when <string> in findbyname(<string>) does not match. Shame on rpm.
        try:
            if self.oldrpm:
                #
                # Old rpm leak memory, so we need to reset the database.
                # This takes some time, but is faster with readonly.
                # 
                del self.db
                self.db = rpm.opendb(False, self.root)
            
                # Check for package first.
                index = self.db.findbyname(resource)
                # If there was no matching package, check for capability.
                if len(index) < 1:
                    index = self.db.findbyprovides(resource)
                    
                # Last, check for file.
                if len(index) < 1:
                    index = self.db.findbyfile(resource)
                for i in index:
                    #
                    # anybody is ok:
                    #
                    header = self.db[i]
                    foundheaders.append(header)
            else:
                # Check for package first.
                headers = self.db.dbMatch('name',str(resource))
                # If there was no matching package, check for capability.
                if headers.count() < 1:
                    headers = self.db.dbMatch('providename', str(resource))
                # Last, check for file.
                if headers.count() < 1:
                    headers = self.db.dbMatch('basenames', str(resource))

                for header in headers:
                    foundheaders.append(header)

            #
            # Now the logic:
            #
            if len(foundheaders) == 0:
                    return valids, invalids
                            
            for header in foundheaders:
                if not checkver:
                    rpmname = header[rpm.RPMTAG_NAME]
                    package = self.get_package(rpmname)
                    valids.append(self.get_package(rpmname))
                    continue
                
                rpmname = header[rpm.RPMTAG_NAME]
                installedpackage = self.get_package(rpmname)
                #
                # we might have conflicts or provides specifying version:
                #
                checkoperator = ">="
                if operator:
                    checkoperator = operator
                if rpmname == resource:
                    #
                    # We ask for a specific version of the resource, so 
                    # we must create a package-like dict we can use for 
                    # comparison:
                    #
                    epoch, version = self._version_split(version)
                    
                    resourcepackage = { 'name': resource,
                                        'version': version,
                                        'release': release,
                                        'epoch': epoch }
                        
                    compres = self.version_compare(installedpackage, 
                                                resourcepackage)

                    if compres >= 0 and ( checkoperator == '>=' or 
                                            checkoperator == '=>'):
                        valids.append(installedpackage)
                    if compres <= 0 and ( checkoperator == '<=' or 
                                            checkoperator == '=<'):
                        valids.append(installedpackage)
                    elif compres < 0 and checkoperator == '<':
                        valids.append(installedpackage)
                    elif compres > 0 and checkoperator == '>':
                        valids.append(installedpackage)
                    elif compres == 0 and checkoperator == '=':
                        valids.append(installedpackage)
                    else:
                        invalids.append(installedpackage)
                else:
                    #
                    # The package just provides this resource, or does not
                    # forfill the version requirement:
                    # Think checking version here is overkill.
                    #
                    invalids.append(installedpackage)


            return valids, invalids
        except rpm.error, message:
            raise ex.query_error, message
        except:
            raise

    def get_requires(self, name):
        ''' return list of names of packages that needs this installed 
            package. Empty list if none, or package not installed'''
        requires = []
        resources = []
        tempreq = {}
        
        #
        # check if package is installed, return if not
        #
        if not self.is_installed(name) == 2:
            return requires

        #
        # check which resources the installed package provides:
        #
        package = self.get_package(name)
        resources.append(name)
        for resource in package['provides']:
            resources.append(resource)
        for file in package['filelist']:
            resources.append(file)
        

        #
        # get list of packages which requires one or more of these resources
        # add them to requires list
        #
        hdrs = self._getinstalledheaders()
        for hdr in hdrs:
            for require in hdr[rpm.RPMTAG_REQUIRENAME]:
                if require in resources:
                    if not tempreq.has_key(hdr['name']):
                        tempreq[hdr['name']] = True

        for name in tempreq.keys():
            requires.append(name)


        #
        # return list:
        #
        
        return requires

    def erase(self, packagenames):
        'Erase packages.'

        if self.oldrpm:
            names = ""
            for package in packagenames:
                names = package + " " + names
            command = "rpm -e %s\n" %names
            fd = os.popen(command)
            output = fd.read()
            exitval = fd.close()
            if exitval:
                message = "Error while removing packages:\n" +\
                    "Exitcode: %s\nOutput: %s\n\n" %(exitval, output)
                sys.stderr.write(message)
            return None
        else:
            ts = rpm.TransactionSet(self.root)
            ts.setVSFlags(~(rpm.RPMVSF_NODSA|rpm.RPMVSF_NORSA))

        ts_names = ""
        for package in packagenames:
            ts_names += package + ' '
            try:
                ts.addErase(package)
            except rpm.error:
                raise ex.not_installed_error, package
        deps = ts.check()
        if deps:
            deps_message = ""
            for ((name, version, release), (reqname, reqversion),
                 flags, suggest, sense) in deps:
                if sense == rpm.RPMDEP_SENSE_REQUIRES:
                    if reqversion == "" or reqversion == None:
                        deps_message += \
                            "\t'%s' requires '%s'.\n" % \
                            (name, reqname)
                    else:
                        deps_message += \
                            "\t'%s' requires '%s' version '%s'.\n"% \
                            (name, reqname, reqversion)
            raise ex.erase_error, \
                ":\n\t%s\n%s\n" % (ts_names, deps_message) \
        # Erase the rpms
        errors = ts.run(self._erase_callback, '')
        if errors:
            error_description = "RPM: "
            for error in errors:
                error_description = error_description + str(error[0]) + "\n"
            raise ex.install_error(error_description, ts_names)
            

    
    def install(self, transaction):
        'Install rpm packages given a dictionary of packages.'

        # Check that all packages are available.
        if (len(transaction) < 1) or not transaction:
            raise ex.install_error, "unrecogniced transaction format."
        missingfiles = []
        for package in transaction.values():
            if not package.has_key('localfilename'):
                msg = "%s has no 'localfilename'" %package['name']
                missingfiles.append(msg)
                continue
            if not os.path.isfile(package['localfilename']):
                missingfiles.append(package['localfilename'])
        if len(missingfiles) > 0:
            raise ex.install_error("Missing files",missingfiles)

        if self.oldrpm:
            ts = rpm.TransactionSet(self.root, self.db)
        else:
            ts = rpm.TransactionSet(self.root)
            ts.setVSFlags(~(rpm.RPMVSF_NODSA|rpm.RPMVSF_NORSA))

        self.filenames = {}
        self.modes = {}
        ts_names = []

        for package in transaction.values():
            if package['flag'] == "upgrade":
                transactionmode = "u"
            elif package['flag'] == "install":
                transactionmode = "i"
            else:
                errmsg = "Mode '%s' for package '%s' not recognized." \
                      % (package['flag'], package['name'])
                raise ex.install_error(errmsg)
            fd = os.open(package['localfilename'], os.O_RDONLY)
            try:
                if self.oldrpm:
                    hdr = rpm.headerFromPackage(fd)[0]
                else:
                    headerts = rpm.TransactionSet(self.root)
                    headerts.setVSFlags(~(rpm.RPMVSF_NODSA|rpm.RPMVSF_NORSA))
                    hdr = headerts.hdrFromFdno(fd)
            except rpm.error, e:
                if str(e) == 'public key not available':
                    self.log.write_stdout('\nThe public key associated with this package was not found.\n\n')
          
            self.filenames[hdr[rpm.RPMTAG_NAME]] = package['localfilename']
            self.modes[hdr[rpm.RPMTAG_NAME]] = package['flag']
            os.close(fd)
            if self.oldrpm:
                ts.add(hdr, hdr, transactionmode)
            else:
                #RPM>=4.1 needs this
                ts.addInstall(hdr, hdr, transactionmode)
            ts_names.append(package['name'])

        # Check dependencies (If there are any dependencies, there must be
        # something wrong with the SPI-files).
        if self.oldrpm:
            deps = ts.depcheck()
        else:
            deps = ts.check()
        ts.order()
        if deps:
            deps_message = ""
            for ((name, version, release), (reqname, reqversion),
                 flags, suggest, sense) in deps:
                if sense == rpm.RPMDEP_SENSE_REQUIRES:
                    if reqversion == "" or reqversion == None:
                        deps_message +=  \
                            "\tPackage '%s' requires '%s'.\n" % \
                            (name, reqname)
                    else:
                        deps_message += \
                            "\tPackage '%s' requires '%s' version '%s'.\n"% \
                            (name, reqname, reqversion)
            raise ex.install_error(deps_message,ts_names)
        #
        # FIXME: Check for local conflicts and give nice output like the 
        # above dep check. This is interesting because of possible file
        # conflicts filling the console, thus making it hard to see the
        # real problem....
        #


        
        # Install the rpms
        if self.oldrpm:
            errors = ts.run(0, 0, self._install_callback, '')
        else:
            #RPM>=4.1 needs this
            errors = ts.run(self._install_callback, '')
        if errors:
            error_description = "RPM: "
            for error in errors:
                error_description += str(error[0]) + "\n"
            raise ex.install_error(error_description, ts_names)
        else:
            #this means all is good. We now flush the rpms that was installed,
            #so they won't fill the cache with unneeded dat, if the user didn't
            #set flush_installed to "no".
            if self.config['flush_installed'] == 'yes':
                from swuplib.download import Flush
                flush = Flush(self.config)
                flush.flush_transaction(transaction)

            
            
    def is_installed(self, package):
        pkgdict = False
        try:
            name = package['name']
            pkgdict = True
        except AttributeError:
            name = package
            pass
        except TypeError:
            name = package
            pass
        if not self.get_package(name):
            return -2
        #
        # only check version if package is dict:
        #
        if not pkgdict:
            #
            # package is installed and we cant check version
            #
            return 2
        return self.version_compare(package, self.get_package(name))

    def version_compare(self, package1, package2, conflict=False):
        
        epoch1 = '0'
        epoch2 = '0'
        version1 = package1['version']
        if package1.has_key('epoch') and package1['epoch']:
            epoch1 = package1['epoch']
        elif ":" in version1:
            epoch1, version1 = self._version_split(version1)
        release1 = package1['release']

        version2 = package2['version']
        if package2.has_key('epoch') and package2['epoch']:
           epoch2 = package2['epoch']
        elif ":" in version2:
            epoch2, version2 = self._version_split(version2)
        release2 = package2['release']
        if conflict and not release2:
            release1 = release2
        return self._version_cmp((epoch1, version1, release1),
                                 (epoch2, version2, release2))
    def system_version(self):
        if self.oldrpm:
            index = self.db.findbyprovides('release')
            releasever = 'Null'
            for i in index:
                header = self.db[i]
                releasever = header['version']
        else:
            ts = rpm.TransactionSet(self.root)
            ts.setVSFlags(~(rpm.RPMVSF_NODSA|rpm.RPMVSF_NORSA))
            idx = ts.dbMatch('provides', 'release')
            # we're going to take the first one - if there is more than one of
            # these then the user needs a beating
            if idx.count() == 0:
                releasever = 'Null'
            else:
                hdr = idx.next()
                releasever = hdr['version']
        return releasever

    def opendb_readwrite(self):
        if self.oldrpm:
            del self.db
            self.db = rpm.opendb(True, self.root)

    def _version_cmp(self, (e1,v1,r1), (e2,v2,r2)):
        """Compare two (<epoch string>, <version string>, <release string>)
        -tuples. Returns > 0 if the first is greater, 0 if they are equal, 
        and < 0 if the first is smaller."""

        def rpmOutToStr(arg):
            if type(arg) == types.ListType:
                if len(arg) == 0:
                    arg = 'None' 
                else:
                    arg = str(arg[0])
            if type(arg) not in types.StringTypes and arg != None:
                arg = str(arg)
            elif arg == None:
                arg = 'None'
            return arg

        e1 = rpmOutToStr(e1)
        v1 = rpmOutToStr(v1)
        r1 = rpmOutToStr(r1)
        e2 = rpmOutToStr(e2)
        v2 = rpmOutToStr(v2)
        r2 = rpmOutToStr(r2)


        result = rpm.labelCompare((e1,v1,r1),(e2,v2,r2))
        if result > 0:
            return 1
        elif result < 0:
            return -1
        else:
            return result


    def _alphanum_split(self, instr):
        """Split groups of alphabetic and integer characters in a string into
        a list of blocks of strings and integers."""
        nonnum_regexp = re.compile("\D+")
        strlen = len(instr)
        cursor = 0
        endpos = cursor
        retlist = []
        while cursor < strlen:
            reobj = nonnum_regexp.search(instr, cursor)
            if reobj:
                startpos = reobj.start()
                endpos = reobj.end()
                if cursor < startpos:
                    retlist.append(int(instr[cursor:startpos]))
                retlist.append(instr[startpos:endpos])
                cursor = endpos
            else:
                retlist.append(int(instr[cursor:]))
                break
        return retlist




    def _list2d_cmp(self, list0, list1):
        """Compare two 2D lists, return -1, 0 , 1 if first list is
        less, equal or greater respectively."""

        n_list0, n_list1 = len(list0), len(list1)
        
        if n_list0 < n_list1:
            n_elements = n_list0
            longer_list = -1
        elif n_list0 > n_list1:
            n_elements = n_list1
            longer_list = 1
        else:
            n_elements = n_list0
            longer_list = 0
            
        for i in range(n_elements):
            n_list0_i, n_list1_i = len(list0[i]), len(list1[i])
            if n_list0_i < n_list1_i:
                nsubelements = n_list0_i
                longer_subelement = -1
            elif n_list0_i > n_list1_i:
                nsubelements = n_list1_i
                longer_subelement = 1
            else:
                nsubelements = n_list0_i
                longer_subelement = 0
            
            for j in range(nsubelements):
                element_0 = list0[i][j]
                element_1 = list1[i][j]
                if element_0 < element_1:
                    return -1
                elif element_0 > element_1:
                    return 1


            if longer_subelement != 0:
                return longer_subelement
        return longer_list


    def _getinstalledheaders (self):
        hdrs = []
        if self.oldrpm:
            key = None
            try:
                key = self.db.firstkey()
            except:
                pass
            while key:
                hdrs.append(self.db[key])
                key = self.db.nextkey(key)
        else:
            #RPM>=4.1 Needs this
            hdrs = self.db.dbMatch()
        return hdrs

    def _create_package(self, rpmheader):
        ''' Creates package dict from rpmheader'''
        dict = {}
        dict["requires"] = rpmheader[rpm.RPMTAG_REQUIRENAME]
        dict["name"] = rpmheader[rpm.RPMTAG_NAME]
        dict["version"] = rpmheader[rpm.RPMTAG_VERSION]
        dict["provides"] = rpmheader[rpm.RPMTAG_PROVIDENAME]
        dict["release"] = rpmheader[rpm.RPMTAG_RELEASE]
        dict["epoch"] = rpmheader[rpm.RPMTAG_EPOCH]
        dict["serial"] = rpmheader[rpm.RPMTAG_SERIAL]
        dict["filelist"] = rpmheader[rpm.RPMTAG_FILENAMES]
        dict["size"] = rpmheader[rpm.RPMTAG_SIZE]
        dict["arch"] = rpmheader[rpm.RPMTAG_ARCH]
        dict["os"] = rpmheader[rpm.RPMTAG_OS]
        dict["description"] = rpmheader[rpm.RPMTAG_DESCRIPTION]
        dict["distribution"] = rpmheader[rpm.RPMTAG_DISTRIBUTION]
        dict["vendor"] = rpmheader[rpm.RPMTAG_VENDOR]
        dict["group"] = rpmheader[rpm.RPMTAG_GROUP]
        dict["source_code"] = rpmheader[rpm.RPMTAG_SOURCERPM]
        dict["build_date"] = time.strftime("%a %b %d %H:%M:%S GMT %Y",
                              time.gmtime(rpmheader[rpm.RPMTAG_BUILDTIME]))
        dict["copyright"] = rpmheader[rpm.RPMTAG_COPYRIGHT]
        dict["summary"] = rpmheader[rpm.RPMTAG_SUMMARY]
        dict["obsoletes"] = rpmheader[rpm.RPMTAG_OBSOLETES]
        conflictname = rpmheader[rpm.RPMTAG_CONFLICTNAME]
        conflictversion = rpmheader[rpm.RPMTAG_CONFLICTVERSION]
        conflictflags = rpmheader[rpm.RPMTAG_CONFLICTFLAGS]
        conflicts = []
        if conflictname:
            # It seems that conflictflags are given as an int if there is
            # only one conflict. We want vectors/lists in all cases.
            if type(conflictflags) is types.IntType:
                conflictflags = [conflictflags]
                
            for i in range(len(conflictname)):
                if conflictversion[i] == "":
                    conflict = "%s" % conflictname[i]
                else:
                    conflict = "%s %s %s" % (conflictname[i],
                                             self._flag2str(conflictflags[i]),
                                             conflictversion[i])
                conflicts.append(conflict)
        dict["conflicts"] = conflicts

        unwantedrequires = self._rpmlib_hack()
        for req in unwantedrequires:
            try:
                #Remove special rpmlib() requirements that was 
                # added by rpmlib we don't need to handle them
                if dict["requires"]:
                    dict["requires"].remove(req)
            except ValueError:
                # python raises exception if not found. Doesn't matter
                pass
            except:
                raise
        requirename = rpmheader[rpm.RPMTAG_REQUIRENAME]
        requireversion = rpmheader[rpm.RPMTAG_REQUIREVERSION]
        requireflags = rpmheader[rpm.RPMTAG_REQUIREFLAGS]
        requirements = []
        if requirename:
            if type(requireflags) == types.IntType:
                requireflags = [requireflags]
            for i in range(len(requirename)):
                if requireversion[i] == "":
                    requirement = "%s" % requirename[i]
                else:
                    requirement = "%s %s %s" % (requirename[i],
                                            self._flag2str(requireflags[i]),
                                            requireversion[i])
                if not requirename[i] in unwantedrequires:
                    #Only add if not a special rpmlib() requirements 
                    #hich only rpm itself knows how to handle right.
                    requirements.append((requirename[i],requirement))
        dict["requirements"] = requirements
        
        #
        # Return dict
        #

        return dict

    def _rpmlib_hack(self):
        provides = []
        provides.append("rpmlib(ScriptletInterpreterArgs)")
        provides.append("rpmlib(PartialHardlinkSets)")
        provides.append("rpmlib(ExplicitPackageProvide)")
        provides.append("rpmlib(PayloadFilesHavePrefix)")
        provides.append("rpmlib(PayloadIsBzip2)")
        provides.append("rpmlib(CompressedFileNames)")
        provides.append("rpmlib(VersionedDependencies)")

        return provides


    def _check_conflict_versions(self, pkg, flag, conflict):
        comp = self.version_compare(pkg, conflict, conflict=True)

        flag = map(None, flag)
        
        if (comp == 0) and ("=" in flag):
            return True

        elif (comp < 0) and ("<" in flag):
            return True

        elif (comp > 0) and (">" in flag):
            return True
        

    def _generate_installed(self):
        if not self.packages:
            pkgdata = {}
            #conflictdata = {}
            conflictordata = {}
            hdrs = self._getinstalledheaders()
            for hdr in hdrs:
                name = hdr[rpm.RPMTAG_NAME]

                if hdr[rpm.RPMTAG_CONFLICTNAME]:
                    conflictnames = hdr[rpm.RPMTAG_CONFLICTNAME]
                    conflictversions = hdr[rpm.RPMTAG_CONFLICTVERSION]
                    conflictflags = hdr[rpm.RPMTAG_CONFLICTFLAGS]
                    #
                    # This is a dict of packages which the installed packages
                    # conflicts against:
                    #
                    #FIXME Why was this done before? 
                    #FIXME Why isn't it needed anymore?
                    #for i in range( len(conflictnames) ):
                    #    conflictname = conflictnames[i]
                    #    if conflictdata.has_key( conflictname ):
                    #        conflictdata[conflictname] = \
                    #            self.get_package(conflictname) 
                    #        conflictdata[conflictname]['flag'] = conflictflags
                    #
                    # This is a dict of installed packages which conflicts with
                    # their respective key:
                    #
                    for i in range( len(conflictnames) ):
                        conflictname = conflictnames[i]
                        conflictversion = conflictversions[i]
                        conflictflag = self._flag2str(conflictflags)
                        epoch, version, release = \
                                self._version_release_split(conflictversion)
                        conflictdict = {
                                    'name': conflictname,
                                    'version': version,
                                    'release': release,
                                    'epoch': epoch,
                                    'flag': conflictflag,
                                    'package': self.get_package(conflictname)}
                        
                        if not conflictordata.has_key( conflictname ):
                            conflictordata[conflictname] = []
                        conflictordata[conflictname].append(conflictdict)
                        
                pkgdata[name] = self.get_package(name)

            #self.conflicts = conflictdata
            self.conflictors = conflictordata
            self.packages = pkgdata
    
    def _generate_db_latest(self):
        """ Generate dict of the installed packages. We might need conflicts
            as well in a later time."""
        if not self.latest:
            latest = {}
            hdrs = self._getinstalledheaders()
            for hdr in hdrs:
                name = hdr[rpm.RPMTAG_NAME]
                pkg = self._create_package(hdr)
                pkg['local'] = True
                latest[name] = pkg
            self.latest = latest

    def __del__(self):
        try:
            if self.db:
                del self.db
            if self.fd != 0:
                os.close(self.fd)
        except AttributeError:
            pass
        except:
            raise

    def _erase_callback(self, what, bytes, total, h, user):
        '''RPM uses this callback to report back to python.'''
        if what == rpm.RPMCALLBACK_UNINST_START:
            message = "Erasing %s - " % (h)
            self.log.write_tty( message )
        if what == rpm.RPMCALLBACK_UNINST_STOP:    
            message = "\rErasing %s - done.\n" % (h)
            self.log.write_tty( "\r"+ " "*80 )
            self.log.write_tty( message )
            message = "Erased %s.\n" % (h)
            self.log.write_syslog_info( message )
    
    def _install_callback(self, what, bytes, total, h, user):
        if what == rpm.RPMCALLBACK_INST_OPEN_FILE:
            name = h[rpm.RPMTAG_NAME]
            filename = self.filenames[name]
            mode = self.modes[name]
            shortname = os.path.basename(filename)
            progress = "Installing %s %s %s %s" %(shortname, 
                self.config['prog_total'], bytes, total)
            self.log.write_progress(progress)

            tty_mode = TTY_MODETEXT[mode]
            self.log.write_tty( "\r"+ " "*80 )
            message = "\r%s %s - " % (tty_mode, name)
            self.log.write_tty( message )
            self.fd = os.open(filename, os.O_RDONLY)
            return self.fd

        elif what == rpm.RPMCALLBACK_INST_CLOSE_FILE:
            name = h[rpm.RPMTAG_NAME]
            mode = self.modes[name]
            self.log.write_tty( "\r"+ " "*80 )
            tty_mode = TTY_MODETEXT[mode]
            message = "\r%s %s - done\n" % \
                      (tty_mode, name)
            self.log.write_tty( message )

            log_mode =  LOG_MODETEXT[mode]
            message = "%s %s." % (log_mode, name)
            self.log.write_syslog_info( message )

            if not self.log.isatty_stdout:
                self.log.write_stdout( message )
                
            os.close(self.fd)
            self.fd = 0
        elif self.cb_count >= self.cb_limit:
            self.cb_count = 0
            try:
                name = h[rpm.RPMTAG_NAME]
                filename = self.filenames[name]
                mode = self.modes[name]
                tty_mode = TTY_MODETEXT[mode]
                self.log.write_tty( "\r"+ " "*80 )
                shortname = os.path.basename(filename)
                progress = "Installing %s %s %s %s" %(shortname, 
                        self.config['prog_total'], bytes, total)
                self.log.write_progress(progress)
                percent = bytes/float(total) * 100 
                intro = "%s %s" %(tty_mode, name)
                if percent < 100:
                    (read, read_prefix) = utils._byte_convert(bytes)
                    (total_read, total_read_prefix) = utils._byte_convert(total)
                    message="\r%-49s (%-7s%-1sB of %-7s%-1sB, %-3d%%)"  \
                        %(intro[:49], read, read_prefix, total_read, 
                            total_read_prefix, percent)
                else:
                    message = "\r%s Running scripts:" %intro 
                self.log.write_tty( message )
            except:
                pass
        else:
            self.cb_count += 1
            
    def _flag2str(self, flag):
        try:
            flag = flag[0]
        except TypeError:
            pass
        except:
            raise
                
        retstr = ""
        if flag & int(rpm.RPMSENSE_LESS) :
            retstr += "<"
        if flag & int(rpm.RPMSENSE_GREATER) :
            retstr += ">"
        if flag & int(rpm.RPMSENSE_EQUAL) :
            retstr += "="
        return retstr

    def _version_release_split(self, full_version):
        version = ""
        release = ""
        epoch = ""
        try:
            epoch, version = string.split(full_version, '-')
        except ValueError:
            pass
        
        epoch, version = self._version_split(version)

        return epoch, version, release
        
    def _version_split(self, version):
        epoch = ""
        try:
            epoch, version = string.split(version, ':')
        except ValueError:
            pass

        return epoch, version
