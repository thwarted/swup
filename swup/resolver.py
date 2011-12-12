# $Id: resolver.py,v 1.140 2005/07/01 09:20:32 christht Exp $

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

failed = -1
DEBUG = False



import os, sys, types, string, re
from swuplib import spiparser
from swuplib import utils
from swuplib import ex
from UserDict import UserDict


#some constants
OK = "ok"
INSTALL = "install"
UPGRADE = "upgrade"
FIRST_SAYS_CONFLICT = -1
SECOND_SAYS_CONFLICT = 1

operator_regexp = re.compile("[<=>]+")



class transaction(UserDict):
    def __init__(self, id, pkgdrv, log):
        UserDict.__init__(self)
        self.id = id
        self.pkgdrv = pkgdrv
        self.log = log
        
    def delete(self, package):
        if self.has_key(package['name']):
            self.__delitem__(package['name'])

    def add(self, package):
        if not self.has_key(package["name"]):
            self[package["name"]] = package
        
    def merge(self, trans):
        self.update(trans)

    def members(self):
        return self.values()

    def has_conflicts(self):
        "Check if there are conflicts between packages in the set."
        conflicts = False
        members = self.members()
        if len(members) < 2:
            return conflicts
        
        conlist = []
        skipped = ""
        for i in range(len(members)):
            package_a = members[i]
            skipped = skipped + "%s " %package_a['name']
            for package_b in members[i:]:
                if self.pkgdrv.check_package_conflict(package_a, package_b):
                    conflicts = True
                    conlist.append((package_a['name'], package_b['name']))

        if conflicts:
            message = "Transaction set has internal package conflicts:\n"
            for pkg_a, pkg_b in conlist:
                
                message = message + "'%s' conflicts against '%s'" \
                    %(pkg_a, pkg_b) 
            
            self.log.write_stderr(message)
            self.log.write_syslog_err(message)
        return conflicts
    
    def next_unresolved(self):
        "Get next unresolved package."
        for package in self.members():
            if package["resolved"] == failed:
                raise ex.resolve_error, "Unable to resolve transaction."
            if package["resolved"] != True:
                return package
            else:
                continue




class transactions(UserDict):
    def __init__(self, pkgdrv, log):
        UserDict.__init__(self)
        self._next_id = 0
        self._transactions_handled = []
        self.pkgdrv = pkgdrv
        self.log = log
        
    def members(self):
        return self.values()

    def new(self, package):
        old_id = self.find_package(package['name'])
        if not old_id == None:
            # Package exists in some other transaction already
            return
        id = self._next_id
        self._next_id = self._next_id + 1
        
        newtrans = transaction(id, self.pkgdrv, self.log)
        newtrans.add(package)
        self[id] = newtrans
        
    def find_package(self, name):
        "Return the transaction id in which package is found."
        for trans_id in self.keys():
            if self[trans_id].has_key(name):
                return trans_id
        
    def merge(self, id1, id2):
        "Merge two transaction to one transaction given their IDs."
        self[id1].merge(self[id2])
        del(self[id2])

    def get_lists(self):
        lists = []
        for trans in self.values():
            list = []
            for package in trans.members():
                list.append(package)
            lists.append(list)
        return lists

    def get_next_resolve(self):
        keys = self.keys()
        keys.sort()
        for key in keys:
            if key not in self._transactions_handled:
                retval = self[key]
                self._transactions_handled.append(key)
                return retval

    def has_conflicts(self, id1, id2):
        trans1 = self[id1]
        trans2 = self[id2]

        for trans1_package in trans1.members():
            for trans2_package in trans2.members():
                check = self.pkgdrv.check_package_conflict(trans1_package,
                                                 trans2_package)
                if check != False: return check

        # If we get here, there are no conflicts between packages in
        # the two sets.
        return False
                    



class resolver:
    def __init__(self, reader, filter, pkgdrv, download, log, config, latest,
                    emptylist, resources):
        self.filter = filter
        self.reader = reader
        self.pkgdrv = pkgdrv
        self.download = download
        self.log = log
        self.config = config
        self.transactions = transactions(pkgdrv, log)
        self.latest = latest
        self.emptylist = emptylist
        self.manual_upgrade = {}
        self.resources = resources
        self.config['prog_total'] = 0

    def _check_conflict_versions(version_a, flag, version_b):
        comp = utils.version_cmp((version_a, ""), (version_b, ""))
        flag = map(None, flag)

        if (comp < 0) and ("<" in flag):
            return True

        elif (comp == 0) and ("=" in flag):
            return True

        elif (comp > 0) and (">" in flag):
            return True

        else:
            return False
        





    def _check_version(self, offered, operator, required):
        """check_version(offered, operator, required)
        Check if an offered version and release of a package fullfills a
        version requirement. <offered> and <required> must both contain
        the two elements version and release. Operator is one of <=> or a
        combinaton. Returns 1 if offered version and release are adequate,
        returns 0 if not adequate."""

        offered_version, offered_release = offered
        req_version, req_release = required

        retval = False

        if req_version == "None":
            return True

        test = self.pkgdrv.version_compare({"epoch": None,
		    "version": offered_version, 
		    "release": offered_release},
                    {"epoch": None,
             	     "version":req_version, 
		     "release":req_release})

        if (test == 0) and (operator == "="):
            retval = True
        elif (test == 0 or test == 1) and (operator == ">="):
            retval = True
        elif (test == 1) and (operator == ">"):
            retval =  True
        elif (test == -1) and (operator == "<"):
            retval = True
        elif (test ==- 1 or test == 0) and (operator == "<="):
            retval = True
        else:
            retval =  False
        return retval


    def is_installed(self, resource, operator="", version="",
                      release=""):

        valid_providers, invalid_providers =  \
            self.pkgdrv.get_providers(resource, operator, version, release)
        if valid_providers:
            # some of the installed versions are ok:
            return OK
        
        if invalid_providers:
            # None of the installed versions suffice. Upgrade the package.
            return UPGRADE
        
        # this resource is not insalled at all:
        return INSTALL

    def get_resource_datalist(self, resourcedict):
        name = resourcedict['name']
        resourcelist = []
        try:
            resourcelist = self.resources[name]
            if not type(resourcelist) == types.ListType:
                #
                # This is from an old style repository.
                # We need to download the resource' rdf and parse it
                #
                uri = resourcelist
                # Get resource. Get package. Return packagedata.
                filename = self.download(uri, TYPE=2)
                baseuri, basename = os.path.split(uri)
                resourcelist = self.reader.read_resource(filename, baseuri)
                #
                # Update the list with this resource so we dont need to
                # parse the file again.
                #
                self.resources[name] = resourcelist
        except KeyError:
            #
            # Resource is not available! This is not good.
            # We have to return and empty list.
            #
            pass
            
        return resourcelist

    def get_package_data(self, uri):
        baseuri, basename = os.path.split(uri)
        try:
            filename = self.download(uri)
            packagedata = self.reader.read_package(filename, baseuri)
            return packagedata
        except ex.download_error, errmsg:
            words = string.split(uri,'/')
            host = "unknown host"
            if words[2]:
                host = words[2]
            else:
                host = words[3]
            message = "%s\n" %string.strip("%s" %errmsg)
            message += "Unable to download package data.\n"
            message += "Possible reasons:\n"
            message += "- Temporary failure in name resolution.\n"
            message += "- Temporary networking issue.\n"
            message += "- Broken rdf repository.\n"
            message += \
                "Please try again later or notify the owner of '%s'.\n" %host
            sys.stderr.write(message)
            pass


    def make_package(self, package):
        name = package["name"]
        if not self.filter(name):
            raise ex.filter_exclude_error, \
                  '\nPackage skipped due to config rule: %s.' % name
        else:
            return package

    def init_packages(self, packages):
        for package in packages:
            if package["name"] == 'swup' and \
                    not self.is_installed('swup') == INSTALL:
                packages = []
                packages.append(package) 
                break
            
        npackages = len(packages)
        i = 1

        for package in packages:
            magic_num = 53
            initout = package['name']
            while len(initout) >= magic_num:
                initout = initout[:-1]
            length = magic_num - len(initout)
            self.log.write_tty('\rInitializing: %s' %initout +
                               length*' ' +' (%-4i/%-4i)'
                               % (i, npackages))
            progress = "Initializing: %s %s %s" %(initout, i,npackages)
            self.log.write_progress(progress)
            i += 1
            try:
                filename = self.download(package["uri"],  \
                                    package["signature_uri"], TYPE=2)
            except ex.download_error, errmsg:
                errmsg = "%s" % errmsg + "Skipping '%s'" %package["uri"]
                self.log.write_syslog_err( errmsg )
                self.log.write_stderr( errmsg ) 
                continue
            (baseuri, basename) = os.path.split(package["uri"])

            packagedata = self.reader.read_package(filename, baseuri)
            packagedata["flag"] = package["flag"]
            packagedata["resolved"] = package["resolved"]
            packagedata["signature_uri"] = "%s.asc" %packagedata["uri"]


            # Check if package exists in a transaction to avoid duplicates.
            if self.transactions.find_package(packagedata['name']):
                continue

            # Create a new package and a new transaction. Add the package
            # to the transaction.
            package = None
            try:
                package = self.make_package(packagedata)
            except ex.filter_exclude_error,e:
                message = e
                message += "Skipping '%s'\n" %packagedata['name']
                sys.stderr.write(message)
                continue
            package, remove = self.swup_specific(package)
            if not remove:
                self.transactions.new(package)
                self.config['prog_total'] += 1
            

    def resolve(self, trans, obsoletors, packages, n_trans):
        self.obsoletors = obsoletors
        self.packages = packages
        self.n_trans = n_trans
        self.swupgrade = False
        self.autoboot = False

        #
        # Test if swup itself is amongst the packages:
        #
        
        if self.packages.has_key('swup'):
            mode = self.is_installed('swup')
            if not mode == INSTALL:
                #
                # Swup is already installed and set for upgrade.
                # It should be upgraded alone.
                #
                self.config["local_first"] = "yes"
                self.swupgrade = True
        
        package = trans.next_unresolved()
        while package:

            if not package:
                return

            reqindex = 0
            progress = "Resolving %s %s %s %s" \
                %(package['name'], self.config['prog_total'],
                    reqindex, len(package["requirements"]))
            self.log.write_progress(progress)
            if self.manual_upgrade.has_key(package['name']):
                trans.delete(package)
                package = trans.next_unresolved()
                continue
            tmppackage = None
            try:
                tmppackage = self.make_package(package)
            except ex.filter_exclude_error,e:
                message = e
                message += "Skipping: '%s'\n" %package['name']
                sys.stderr.write(message)
                trans.delete(package)
                # FIXME: what happens with other packages in this transaction?
                package = trans.next_unresolved()
                continue

            tmppackage, remove = self.swup_specific(tmppackage)
            if remove:
                trans.delete(package)
                package = trans.next_unresolved()
                continue
            package = tmppackage

            #
            # The two next sections will both need this, let's generate once:
            #
            package_name = package['name']
            obsoleted = []
            if self.obsoletors.has_key(package_name):
                obsoleted = self.obsoletors[package_name]
            
            #
            # Check if the package obsoletes some other installed package.
            # If so, set flag to UPGRADE, and add package to upgradeobs
            # 
            # FIXME: what about swup_install-if-upgrade???
            upgradeobs = []
            for index in range(len(obsoleted)):
                obs = obsoleted[index]
                obs_flag = self.is_installed(obs)
                if not obs_flag == INSTALL:
                    package["flag"] = UPGRADE
                    upgradeobs.append(obs)
                    continue
            #
            # Check if some installed package require the already intalled 
            # version of this package, and also must be checked. 
            # Only interesting for packages with upgrade flag, and only
            # interesting if we found package arument(s) on the command line.
            # Also interesting in the case of swup itself, since the package
            # list then is shrinked.
            # We must take obsoletes into consideration aswell.
            #
            if ( not self.emptylist and package['flag'] == UPGRADE ) or \
                ( self.swupgrade and package['flag'] == UPGRADE ):
                requires = self.pkgdrv.get_requires(package_name)
                scheduled = {}
                for req in requires:
                    if req == package['name']:
                        continue
                    if self.latest.has_key(req):
                        is_inst = self.pkgdrv.version_compare(self.latest[req],
                                            self.pkgdrv.get_package(req))
                        if is_inst == 1:
                            #
                            # FIXME: only include packages if their 
                            # requirements is no longer provided by the package
                            # we are currently resolving.
                            # In most cases this package will still provide the
                            # resource, so the list should not get very big.
                            #
                            scheduled[req] = True
                for obs in upgradeobs:
                    requires = self.pkgdrv.get_requires(obs)
                    for req in requires:
                        if not scheduled.has_key(req):
                            if self.latest.has_key(req):
                                is_inst = self.pkgdrv.version_compare(
                                                    self.latest[req],
                                                    self.pkgdrv.get_package(req)
                                                    )
                                if is_inst == 1:
                                    scheduled[req] = True
                #
                # Ok, let's create a new transaction for these packages
                # if they're not present already:
                # 
                for pkg in scheduled.keys():
                    if not self.transactions.find_package(pkg):
                        if self.manual_upgrade.has_key(pkg):
                            continue
                        #
                        # Ok, lets add this package to the transactions:
                        #
                        pkgdata = self.latest[pkg]
                        pkgdata["signature_uri"] = "%s.asc" %pkgdata['uri']
                        filename = self.download(pkgdata["uri"], 
                                            pkgdata["signature_uri"], TYPE=2)
                        (baseuri, basename) = os.path.split(pkgdata["uri"])
                        packagedata = self.reader.read_package(filename, 
                                                                    baseuri)
                        packagedata["flag"] = UPGRADE
                        packagedata["resolved"] = False
                        packagedata["signature_uri"] = "%s.asc" \
                                                    %packagedata["uri"]
                        try:
                            newpackage = self.make_package(packagedata)
                            self.transactions.new(newpackage)
                            self.config['prog_total'] += 1
                        except ex.filter_exclude_error, e:
                            message = "%s" %e
                            message += "Skipping %s\n" %pkg
                            sys.stderr.write(message)
                        
            
            #
            # Now check for requirements:
            #
            
            requirements = package["requirements"]
            dependency_error = False

            broken_resolving = False
            for requirement in requirements:
                reqindex += 1
                progress = "Resolving %s %s %s %s" \
                    %(package['name'], self.config['prog_total'],
                        reqindex, len(package["requirements"]))
                self.log.write_progress(progress)
                reqname = requirement["name"]
                reqversion = requirement["version"]
                if requirement.has_key('epoch'):
                    if not requirement['epoch'] == None:
                        reqversion = requirement['epoch']+":"+reqversion
                reqrelease = requirement["release"]
                operator = requirement["operator"]
                origreqname = reqname
                origreqversion = reqversion
                origreqrelease = reqrelease
                origoperator = operator
                magic_num = 57
                resout = "%s: %s" %(package['name'],reqname)
                while len(resout) >= magic_num:
                    resout = resout[:-1]
                length = magic_num - len(resout)
                self.log.write_tty("\rResolving %s" %resout\
                                + length*' ' + " (%-4i/%-4i)" %\
                                (trans.id+1, n_trans))

                #
                # If we are going to _install_ the package, we prefer the
                # resources currently installed _before_ the resources
                # provided in the rdfs (the old way. a bit faster):
                #
                if package["flag"] == INSTALL or \
                    self.config["local_first"] == "yes":
                    install_flag = self.is_installed(reqname, '>=',
                                                  reqversion, reqrelease)
                    if install_flag == OK:
                        continue


                #
                # Get the list of alternative packages that provide this
                # resource:
                #
                resourcelist = self.get_resource_datalist(requirement)

                #
                # Try to pick one wizely:
                #
                
                # No good alternative yet:
                pkg_found = False 
                
                # Some lists in which to place different alternatives:
                
                # already installed alternatives that are not excluded:
                okinst = []
                
                # already installed alternatives that are excluded:
                excludedinst = []
                
                # alternatives that are not installed:
                notinst = []
                
                
                for resourcedata in resourcelist:
                    resname = resourcedata['name']
                    resver = resourcedata['version']
                    if resourcedata.has_key('epoch'):
                        if not resourcedata['epoch'] == None:
                            resver = resourcedata['epoch']+":"+resver

                    resrel = resourcedata['release']
                    resuri = resourcedata['uri']
				    
                    if reqname == resname:
                        #
                        # The requirement asks for this exact package.
                        # Now check if it is excluded:
                        #
                        if not self.filter(resname):
                            #
                            # Excluded it was, check if it is
                            # installed and usable: 
                            #
                            install_flag = self.is_installed(reqname, '>=',
                                                    reqversion, 
                                                    reqrelease)
                            if install_flag == OK:
                                pkg_found = True
                                continue
                        #
                        # Not excluded or excluded not ok
                        # 
                        
                        reqversion = resver
                        reqrelease = resrel
                        requri = resuri
                        pkg_found = True
                        continue

                    #
                    # Resource provider may be amongst packages we already 
                    # know will be installed or upgraded.
                    #
                    if packages.has_key(resname):
                        #
                        # Ok then, check if it is excluded:
                        #
                        if not self.filter(resname):
                            #
                            # Excluded it was, so we'll check if the 
                            # installed package is usable: 
                            #
                            install_flag = self.is_installed(reqname, '>=',
                                                    reqversion, 
                                                    reqrelease)
                            if install_flag == OK:
                                pkg_found = True
                                continue
                        #
                        # Not excluded, prefect! :)
                        #
                        reqname = resname
                        reqversion = resver
                        reqrelease = resrel
                        requri = resuri
                        pkg_found = True
                        continue
                    
                    isinstalled = self.is_installed(resname, '>=',
                                                    resver, resrel)
                    if isinstalled != INSTALL:
                        #
                        # Found that an installed package that provide
                        # this resource (or maybe only so if upgraded):
                        #
                        # Now check if it is excluded:
                        #
                        if self.filter(resname):
                            okinst.append(resourcedata)
                        else:
                            excludedinst.append(resourcedata)
                    else:
                        notinst.append(resourcedata)
                
                #
                # Check if any of these already have been marked as not
                # installable:
                #
                
                if not pkg_found and okinst:
                    for alt in okinst:
                        if not self.manual_upgrade.has_key(alt['name']):
                            reqname = alt['name']
                            reqrelease = alt['release']
                            requri = alt['uri']
                            reqversion = alt['version']
                            pkg_found = True
                            break
                    if pkg_found:
                        continue
			
                
                #
                # Use the first good installed alternative:
                #
                
                if not pkg_found and okinst:
                    resourcedata = okinst[0]
                    reqname = resourcedata["name"]
                    reqrelease = resourcedata["release"]
                    requri = resourcedata["uri"]
                    reqversion = resourcedata["version"]
                    if resourcedata.has_key('epoch'):
                        if not resourcedata['epoch'] == None:
                            reqversion = resourcedata['epoch']+":"+reqversion
                    pkg_found = True
                    continue
                    
                #
                # No good installed packages found. 
                # 
                # If there where any excluded packages which provides the 
                # correct version of the requirement, we wont have to do 
                # anything since they wont be upgraded anyway:
                #
                    
                if not pkg_found and excludedinst:
                        install_flag = self.is_installed(reqname, '>=',
                                                    reqversion, reqrelease)
                        if install_flag == OK:
                            pkg_found = True
                            continue
                
                if not pkg_found:
                    #
                    # No usable installed packages found.
                    # We must look for packages that are not already 
                    # installed. :(
                    #
                    
                    # Look for packages not excluded:
                    excluded = []
                    for resourcedata in notinst:
                        resname = resourcedata["name"]
                        if self.filter(resname):
                            # Not excluded? 
                            # Well then, let's use it. :)
                            reqname = resname
                            reqversion = resourcedata["version"]
                            reqrelease = resourcedata["release"]
                            requri = resourcedata["uri"]
                            pkg_found = True
                            continue
                        else:
                            # Generate a cute _little_ list of alternatives:
                            excluded.append(resourcedata)
                    
                    if not pkg_found:
                        #
                        # Still no luck. 
                        #
                        # First alternative is chosen, even though it is 
                        # excluded, and not already installed.. This will be
                        # caught when we try to create a package object
                        # using this data.
                        #
                        try:
                            resourcedata = resourcelist[0]
                            pkg_found = True
                        except IndexError:
                            #
                            # In some cases we will still not have found any
                            # resource provides, espessially if the resources
                            # are somewhat broken. In this case we need to
                            # check if the local system may have the
                            # requirement installed:
                            #
                            install_flag = self.is_installed(reqname, '>=',
                                                                reqversion, 
                                                                reqrelease)
                            if install_flag == OK:
                                continue
                            else:
                                message = "\nNo available package provides: " \
                                    + "%s %s %s-%s\n" \
                                    %(reqname, operator, reqversion, reqrelease)
                                sys.stderr.write(message)
                                broken_resolving = True
                                break
                        reqname = resourcedata["name"]
                        reqversion = resourcedata["version"]
                        if resourcedata.has_key('epoch'):
                            if not resourcedata['epoch'] == None:
                                reqversion = resourcedata['epoch']+":"+reqversion
                        reqrelease = resourcedata["release"]
                        requri = resourcedata["uri"]
               
                    
                #
                # Check if the package matching the enhanced resource is 
                # already installed, very often it is.
                #
                install_flag = self.is_installed(reqname, '>=',
                                                  reqversion,
                                                  reqrelease)
                if install_flag == OK:
                    continue
            
                #
                # Time to check for duplicates in other transactions:
                #

                #
                # First we make sure we use the package in the Merged latest
                # and not any outdated linked package:
                #
                if self.latest.has_key(reqname):
                    reqpackage = self.latest[reqname]
                    reqversion = reqpackage['version']
                    reqrelease = reqpackage['release']
                else:
                    message = "Picked resource provider not found amongst "\
                            "latest.\nThis should never happen."
                    sys.stderr.write(message)
                    sys.exit(1)
                
                #
                # Should package be filtered out?
                #
                newpkgdata = self.get_package_data(requri)
                if not newpkgdata:
                    broken_resolving = True
                    break
                newpkgdata['flag'] = install_flag
                try:
                    newpackage = self.make_package(newpkgdata)
                except ex.filter_exclude_error,e:
                    sys.stderr.write(str(e))
                    broken_resolving = True
                    break
                     
                #
                # Check if required package cant be upgraded due to manual-
                # upgrade flag:
                #
                if self.manual_upgrade.has_key(reqname):
                    broken_resolving = True
                    break
                newpackage, remove = \
                      self.swup_specific(newpackage)
                if remove:
                    broken_resolving = True
                    break
                    

                #
                # Check if required package is already set for upgrade or
                # install.
                #

                pending_trans_id = self.transactions.find_package(reqname)

                if pending_trans_id != None:
                    pending_trans = self.transactions[pending_trans_id]
                    pending_pkg = pending_trans[reqname]

                    #
                    # Merge packages in same transaction.
                    #
                    if not trans.id == pending_trans.id:
                        self.transactions.merge(trans.id, pending_trans.id)
                
                #
                # The package was not in any pending transactions.  We
                # must add the package to the transaction.
                #
                elif install_flag in [INSTALL, UPGRADE]:
                    pkgdata = self.get_package_data(requri)
                    if not pkgdata:
                        broken_resolving = True
                        break
                    pkgdata["flag"] = install_flag
                    pkgdata["resolved"] = False
                    pkgdata["signature_uri"] = "%s.asc" %pkgdata['uri']
                    newpackage = None
                    try:
                        newpackage = self.make_package(pkgdata)
                    except ex.filter_exclude_error,e:
                        #
                        # Package depends upon a package that is caught
                        # by the exclude filter. We should notify the user,
                        # and skip this transaction.
                        #
                        message = e
                        message += "Selected package '%s' " %package['name']\
                            + "depends upon " \
                            + "excluded package '%s'\n" %pkgdata['name'] \
                            + "Skipping '%s'\n" %package['name']
                        sys.stderr.write(message)
                        broken_resolving = True
                        break
                    install_flag = self.is_installed(origreqname, '>=',
                                                  origreqversion,
                                                  origreqrelease)
                    if install_flag == OK:
                        self.transactions.new(newpackage)
                        self.config['prog_total'] += 1
                    else:
                        #
                        # We actually depend upon this exact version:
                        #
                        # FIXME: Sorted transactions.
                        # Create new transaction and add a 
                        # 'Requires' on that transaction to this 
                        # transaction.
                        trans.add(newpackage)
                        self.config['prog_total'] += 1

                else:
                    # We should never get here. This means the install_flag
                    # is illegal.
                    raise ex.coder_messed_up_error, \
                          "Illegal install flags for package %s: '%s'" % \
                          (reqname, install_flag)

            if broken_resolving:
                package['resolved'] = failed
            else:
                package["resolved"] = True
            package = trans.next_unresolved()

        
        #
        # Notify the calling process what happened:
        #
        if self.swupgrade:
            return 1
        elif self.autoboot:
            return 2

    def swup_specific(self, package):
        """
        Check if a package has special needs. This may be that the package 
        should not be upgraded, but rather installed in addition to the 
        other packages, or that the upgrade needs some kind of human 
        interference.

        returns the following: (package, remove)
        package (maybe modified version of input)
        remove, boolean, signals if the package should not be used
        """

        #
        # Check if the package has special needs:
        #

        remove = False
        #
        # We only care about packages that are giong to be upgraded:
        #
        if package["flag"] != UPGRADE:
            return (package, remove)
        
        for conflict in package["conflicts"]:
            # Get conflict information:
            import types
            if type(conflict) is types.DictType:
                conflictname = conflict["name"]
                conflictflag = conflict["flag"]
                conflictversion = conflict["version"]+"-"+conflict["release"]

            # Maybe it must not be upgraded, but installed?  Some
            # packages should not be upgraded, but installed in
            # addition to the old one. Ex: kernels.
            if conflictname == "swup_install-if-upgrade":
                package["flag"] = INSTALL
                
            # Maybe it must not be upgraded automaticly at all?  Some
            # upgrades should involve human interference, like major
            # backward incompatible database changes.
            if conflictname == "swup_manual-upgrade":
                if self.config['force'] == "yes":
                    continue
                manual = True
                
                if conflictversion:
                    # This test triggered, this means we must check if
                    # local installed package should trigger manual
                    # upgrade:
                    cver, crel = string.split(conflictversion, '-')
                    retflag = self.is_installed(package['name'], 
                                conflictflag, cver, crel)
                    if retflag != OK:
                        #
                        # Installed package is not within range for 
                        # manual-upgrade. Let's leave it as it is
                        #
                        manual = False
                if manual:
                    remove = True
                    self.manual_upgrade[package['name']] = True
                    message = \
                    "\nPackage '%s' is excluded from being upgraded.\n" \
                        %package['name'] +\
                    "This happens because it requires some level of human "+\
                    "interaction to be\nupgraded correctly. Please read the "+\
                    "errata for this package for more\ninformation on "+\
                    "what kind of interaction is needed.\n"+\
                    "To force upgrade of this package in spite of this "+\
                    "warning add:\n --force\nas command line option to swup.\n"
                    self.log.write_stderr(message)
                    self.log.write_syslog_err(message)
            
            # Maybe it needs a reboot?
            if conflictname == "swup_auto-reboot":
                self.autoboot = True

        return (package, remove)

    def check_conflicts_in_set(self, id):
        trans = self.transactions[id]
        if trans.has_conflicts():
            return True
        else:
            return False


    def check_conflicts_between_sets(self):
        ids = self.transactions.keys()
        deleted_ids = []

        for id1 in ids:
            if id1 in deleted_ids: continue
            for id2 in ids:
                if id1 == id2: continue
                if id2 in deleted_ids: continue
                check = self.transactions.has_conflicts(id1, id2)
                if check == FIRST_SAYS_CONFLICT:
                    deleted_ids.append(id1)
                    break
                if check == SECOND_SAYS_CONFLICT:
                    deleted_ids.append(id2)

        return deleted_ids


    def check_local_conflicts(self):
        ids = self.transactions.keys()
        deleted_ids = []
        for id in ids:
            if id in deleted_ids: continue
            for package in self.transactions[id].members():
                # Checking if local packages report trouble.
                local_conflicts = self.pkgdrv.get_conflicts(package)
                if local_conflicts and len(local_conflicts) > 0:
                    #
                    # Make sure conflict is not amongst packages we will 
                    # upgrade:
                    #
                    real_conflicts = []
                    for conflict in local_conflicts:
                        con = self.transactions.find_package(conflict['name'])
                        if con == None:
                            real_conflicts.append(conflict)
                    local_conflicts = real_conflicts
                if local_conflicts and len(local_conflicts) > 0:
                    skipped = self.transactions[id].keys()
                    skipped = string.join(skipped, ' ')
                    local_conflicts_names = ''
                    for conflictpackage in local_conflicts:
                        #FIXME is this check needed?
                        if type(conflictpackage) is types.DictType:
                            local_conflicts_names += " %s " \
                                    %conflictpackage['name']
                        else:
                            local_conflicts_names += " %s " \
                                    %conflictpackage[0]
                            
                    message = "New package '%s' conflicts " %package['name'] \
                            +"against installed package(s): "\
                            +"%s\n" %local_conflicts_names \
                            +"Skipping packages: %s" %skipped
                    self.log.write_stderr(message)
                    self.log.write_syslog_err(message)
                    deleted_ids.append(id)
                    del self.transactions[id]
                    break
                
                # Checking if new packages report trouble with local ones.
                conflict_locals = self.pkgdrv.get_conflictors(package)
                if conflict_locals and len(conflict_locals) > 0:
                    #
                    # Make sure conflict is not amongst packages we will 
                    # upgrade:
                    #
                    real_conflicts = []
                    for conflictordict in conflict_locals:
                        conflictor = conflictordict['name']
                        con = self.transactions.find_package(conflictor)
                        if con == None:
                            real_conflicts.append(conflictor['package'])
                    conflict_locals = real_conflicts
                
                if conflict_locals and len(conflict_locals) > 0:
                    skipped = self.transactions[id].keys()
                    skipped = string.join(skipped, " ")
                    message = "Installed package(s) %s conflicts with "\
                              "new package '%s'!\n"\
                              "Skipping packages: %s"\
                              % (conflict_locals, package["name"], skipped)
                    self.log.write_stderr(message)
                    self.log.write_syslog_err(message)
                    deleted_ids.append(id)
                    del self.transactions[id]
                    break

        
    def check_conflicts(self):
        # Check for conflicts within a transaction.
        for id in self.transactions.keys():
            if self.check_conflicts_in_set(id):
                skipped = self.transactions[id].keys()
                skipped = string.join(skipped, ' ')
                del self.transactions[id]
                message = "Transaction set has internal conflicts.\n"\
                          "Skipping packages: %s" % skipped
                self.log.write_stderr(message)
                self.log.write_syslog_err(message)

        # Check for conflicts between transactions.
        delete_ids = self.check_conflicts_between_sets()
        if delete_ids:
            skipped = ""
            for id in delete_ids:
                skipped = skipped + " " + \
                          string.join(self.transactions[id].keys(), " ")
                del self.transactions[id]
            if skipped:
                message = "Packages skipped due to conflicts with other"\
                          " new packages:%s" % skipped
                self.log.write_syslog_err(message)
                self.log.write_stderr("\n%s" %message)

        # Check if local system report conflicts. If one is found, check if
        # conflicting local package will be upgraded - that will solve it.
        # Second, check if new package reports conflict with installed
        # package.
        self.check_local_conflicts()
        

    def solve_deps(self, packages, obsoletors):
        self.swupgrade = False
        if not packages: 
            raise ex.empty_package_list_error, "Empty argument for packagelist."
        self.init_packages(packages)
        pkgnames = {}
        #
        # swap from list to dict:
        #
        for package in packages:
            pkgnames[package["name"]] = package["name"]

        trans = self.transactions.get_next_resolve()
        while trans :
            n_transactions = len(self.transactions)
            try:
                self.swupgrade = self.resolve(trans, obsoletors, 
                                    pkgnames, n_transactions)
            except ex.filter_exclude_error, errmsg:
                skipped = string.join(trans.keys(), " ")
                del self.transactions[trans.id]
                message = "%s\nSkipping packages: %s." % (errmsg, skipped)
                self.log.write_stdout(message)
                self.log.write_syslog_err(message)
            except ex.resolve_error:
                skipped = string.join(trans.keys(), " ")
                del self.transactions[trans.id]
                message = "Failed to resolve this transaction.\n" \
                    +"Skipping packages: %s." % skipped
                self.log.write_stderr(message)
                self.log.write_syslog_err(message)
            trans = self.transactions.get_next_resolve()
        outstr = "Checking conflicts -" 
        self.log.write_tty("\r" + outstr + (80-len(outstr))*" ")
        self.check_conflicts()
        self.log.write_tty("\r%s done.\n" %outstr) 

        return self.transactions, self.swupgrade
                

            







