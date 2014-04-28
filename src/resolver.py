# $Id: resolver.py,v 1.9 2001/03/28 15:53:30 olafb Exp $

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

true, false, failed = 1, 0, -1
DEBUG = true



import os, sys, types, string, re
import spiparser, utils

# define some exceptions
DependencyError = 'resolver.DependencyError'
ParseError = 'resolver.ParseError'
Error = 'resolver.Error'
resolve_error = "resolver.resolve_error"
error = 'resolver.error'
config_exclude_error = 'resolver.config_exclude_error'
conflict_error = 'resolver.conflict_error'

#some constants
INSTALL_FLAG = "install"
UPGRADE_FLAG = "upgrade"
OK = "ok"
INSTALL = "install"
UPGRADE = "upgrade"
FIRST_SAYS_CONFLICT = -1
SECOND_SAYS_CONFLICT = 1

operator_regexp = re.compile("[<=>]+")


def _check_conflict_versions(version_a, flag, version_b):
    comp = utils.version_cmp((version_a, ""), (version_b, ""))
    flag = map(None, flag)

    if (comp < 0) and ("<" in flag):
        return true

    elif (comp == 0) and ("=" in flag):
        return true

    elif (comp > 0) and (">" in flag):
        return true

    else:
        return false
    



def _check_package_conflict(package_a, package_b):
    "Check for conflicts between two packages."
    FIRST_SAYS_CONFLICT = -1
    SECOND_SAYS_CONFLICT = 1
    
    if package_a.conflicts:
        for conflict in package_a.conflicts:
            if not conflict: continue
            if conflict.name == package_b.name:
                if not conflict.flag:
                    return FIRST_SAYS_CONFLICT
                elif _check_conflict_versions(package_b.version,
                                              conflict.flag,
                                              conflict.version):
                    return FIRST_SAYS_CONFLICT

    if package_b.conflicts:
        for conflict in package_b.conflicts:
            if not conflict: continue
            if conflict.name == package_a.name:
                if not conflict.flag:
                    return SECOND_SAYS_CONFLICT
                elif _check_conflict_versions(package_a.version,
                                              conflict.flag,
                                              conflict.version):
                    return SECOND_SAYS_CONFLICT

    # If we get here there are no conflict issues between packages.
    return false




def check_version(offered, operator, required):
    """check_version(offered, operator, required)
    Check if an offered version and release of a package fullfills a
    version requirement. <offered> and <required> must both contain
    the two elements version and release. Operator is one of <=> or a
    combinaton. Returns 1 if offered version and release are adequate,
    returns 0 if not adequate."""

    offered_version, offered_release = offered
    req_version, req_release = required

    retval = false

    if req_version == "None":
        return true

    test = utils.version_cmp((offered_version, offered_release),
                              (req_version, req_release))

    if (test == 0) and (operator == "="):
        retval = true
    elif (test == 0 or test == 1) and (operator == ">="):
        retval = true
    elif (test == 1) and (operator == ">"):
        retval =  true
    elif (test == -1) and (operator == "<"):
        retval = true
    elif (test ==- 1 or test == 0) and (operator == "<="):
        retval = true
    else:
        retval =  false
    return retval


class conflict:
    def __init__(self, rule):

        operator = operator_regexp.findall(rule)
        splitlist = operator_regexp.split(rule)
        if len(splitlist) == 2:
            self.name, self.version = splitlist
            self.flag = operator
        elif len(splitlist) == 1:
            self.name = splitlist[0]
            self.flag, self.version = None, None
        else:
            raise Error, "conflict %s invalid" % rule
        


class package:
    def __init__(self, packagedata):
        """__init__(self, packagedata)
        Creates a new package instance from the dictionary packagedata.
        Packagedata must contain 'name', 'version', 'release', 'arch', 'os'
        'uri', 'signature', 'flag', 'conflicts' and 'requirements'."""

        self.name = packagedata["name"]
        self.version = packagedata["version"]
        self.release = packagedata["release"]
        self.arch = packagedata["arch"]
        self.os = packagedata["os"]
        self.uri= packagedata["uri"]
        self.signature_uri = packagedata["signature"]
        self.group = packagedata["group"]
        self.requirements = packagedata["requirements"]
        self.flag = packagedata["flag"]
        self.resolved = false
        self.conflicts = []
        self.localfilename = None
        for item in packagedata["conflicts"]:
            if not item: continue
            newconflict = conflict(item)
            self.conflicts.append(newconflict)




class transaction:
    def __init__(self, id):
        self._members = {}
        self.id = id
        
    def add(self, pkg):
        if not self._members.has_key(pkg.name):
            self._members[pkg.name] = pkg
        
    def merge(self, trans):
        self._members.update(trans._members)

    def members(self):
        return self._members.values()

    def has_key(self, key):
        return self._members.has_key(key)

    def __len__(self):
        return len(self._members)

    def __getitem__(self, key):
        return self._members[key]

    def __del__(self):
        del(self._members)

    def keys(self):
        return self._members.keys()

    def values(self):
        return self._members.values()

    def has_conflicts(self):
        "Check if there are conflicts between packages in the set."
        members = self.members()
        if len(members) < 2:
            return false
        
        for i in range(len(members)):
            package_a = members[i]
            for package_b in members[i:]:
                if _check_package_conflict(package_a, package_b):
                    return true

        # If we get here there are no conflicts.
        return false
    
    def next_unresolved(self):
        "Get next unresolved package."
        for pkg in self.members():
            if pkg.resolved == failed:
                raise self.resolve_error, "Unable to resolve transaction."
            if pkg.resolved != true:
                return pkg
            else:
                continue
        # If all packages are resolved. Return None.
        return None




class transactions:
    def __init__(self):
        self._next_id = 0
        self._transactions = {}
        self._transactions_handled = []
        
    def new(self, pkg):
        id = self._next_id
        self._next_id = self._next_id + 1
        
        newtrans = transaction(id)
        newtrans.add(pkg)
        self._transactions[id] = newtrans
        
    def find_package(self, name):
        "Return the transaction id in which package is found."
        for trans_id in self._transactions.keys():
            if self._transactions[trans_id].has_key(name):
                return trans_id
        # Return None if package is not found.
        return None
        
    def merge(self, id1, id2):
        "Merge two transaction to one transaction given their IDs."
        self._transactions[id1].merge(self._transactions[id2])
        del(self._transactions[id2])

    def keys(self):
        return self._transactions.keys()

    def has_key(self, key):
        return self._transactions.has_key(key)

    def remove(self, id):
        del(self._transactions[id])

    def get_lists(self):
        lists = []
        for trans in self._transactions.values():
            list = []
            for pkg in trans.members():
                list.append([pkg.name, pkg.uri, pkg.flag, pkg.signature,
                             pkg.version, pkg.release])
            lists.append(list)
        return lists

    def values(self):
        return self._transactions.values()

    def __getitem__(self, key):
        return self._transactions[key]

    def get_next_resolve(self):
        keys = self._transactions.keys()
        keys.sort()
        for key in keys:
            if key not in self._transactions_handled:
                retval = self._transactions[key]
                self._transactions_handled.append(key)
                return retval

        # If we get here, all transactions are handled.
        return None

    def __len__(self):
        return len(self._transactions)

    def __delitem__(self, key):
        del self._transactions[key]
        
    def has_conflicts(self, id1, id2):
        trans1 = self._transactions[id1]
        trans2 = self._transactions[id2]

        for trans1_package in trans1.members():
            for trans2_package in trans2.members():
                check = _check_package_conflict(trans1_package,
                                                 trans2_package)
                if check != false: return check

        # If we get here, there are no conflicts between packages in
        # the two sets.
        return false
                    



class resolver:
    def __init__(self, reader, filter, driver, download, log,
                  max_depth=5 ):
        self.filter = filter
        self.reader = reader
        self.driver = driver
        self.download = download
        self.max_depth = max_depth
        self.log = log
        self.transactions = transactions()


    def is_installed(self, resource, operator="", version="",
                      release=""):
        retvals = self.driver.query(resource)
        if not retvals:
            return INSTALL

        if not operator:
            return OK
        
        for retval in retvals:
            (iname, iversion, irelease) = retval
            if release == "": irelease = ""
            if check_version((iversion, irelease), operator,
                              (version, release)):
                return OK
            
        # None of the installed versions suffice. Upgrade the package.
        return UPGRADE


    def get_resource_data(self, uri):

        # Get resource. Get package. Return packagedata.
        filename = self.download(uri)
        baseuri, basename = os.path.split(uri)
        resourcelist = self.reader.read_resource(filename, baseuri)

        # Just pick the first available package in the list of packages.
        resourcedata = resourcelist[0]
        return resourcedata


    def get_package_data(self, uri):
        baseuri, basename = os.path.split(uri)
        filename = self.download (uri)
        packagedata = self.reader.read_package(filename, baseuri)

        return packagedata


    def make_package(self, packagedata):
        name = packagedata["name"]
        group = packagedata["group"]
        if not self.filter(name, group):
            raise config_exclude_error, \
                  'Package skipped due to config rule: %s.' % name
        else:
            return package(packagedata)

    
    def init_packages(self, packages):
        #n_packages = len(pkglist)
        npackages = len(packages)
        i = 1

        for package in packages:
            self.log.write_tty('\rInitializing packages'+
                               50*' ' +'(%-3i/%-3i)'
                               % (i, npackages))
            filename = self.download(package.uri, package.signature_uri)
            (baseuri, basename) = os.path.split(package.uri)

            packagedata = self.reader.read_package(filename, baseuri)
            packagedata["flag"] = package.flag
            name = packagedata["name"]
            version = packagedata["version"]
            release = packagedata["release"]
            group = packagedata["group"]

            # Check if package exists in a transaction to avoid duplicates.
            if self.transactions.find_package(name):
                continue

            # Create a new package and a new transaction. Add the package
            # to the transaction.
            try:
                newpackage = self.make_package(packagedata)
                self.transactions.new(newpackage)
            except config_exclude_error, errmsg:
                message = "Package skipped due to config rule: %s" % name
                self.log.write_stderr(message)
                continue
            except:
                raise
            

    def resolve(self, trans):
        pkg = trans.next_unresolved()
        while pkg:

            if not pkg:
                return

            requirements = pkg.requirements
            dependency_error = false

            for requirement in requirements:
                reqname = requirement["name"]
                reqversion = requirement["version"]
                reqrelease = requirement["release"]
                operator = requirement["operator"]
                install_flag = self.is_installed(reqname, operator,
                                                  reqversion,
                                                  reqrelease)
                
                # If requirement is satisfied on local system, continue
                # with next requirement.
                if install_flag == OK:
                    continue

                # Get the resource and replace name, version and release
                # with the data from the resource.
                resourcedata = self.get_resource_data(requirement["uri"])
                reqname = resourcedata["name"]
                reqversion = resourcedata["version"]
                reqrelease = resourcedata["release"]
                requri = resourcedata["uri"]

                # Check if package is already installed (but somehow does not
                # know that it provides the required resource). If package is
                # installed, continue with next requirement. This is rater
                # ugly, but required for e.g. RPM.
                install_flag = self.is_installed(reqname, '>=',
                                                  reqversion,
                                                  reqrelease)
                if install_flag == OK:
                    continue
                
                # Require pacakge from resource to be identical to the one in
                # a possible other transaction, else ther could be conflicts.
                operator = "="

                # Check if required package is already set for upgrade or
                # install.

                pending_trans_id = self.transactions.find_package(reqname)

                if pending_trans_id != None:
                    pending_trans = self.transactions[pending_trans_id]
                    pending_pkg = pending_trans[reqname]

                    # Check if required package which already is set for
                    # upgrade/install suffice on version/release.
                    if reqrelease:
                        if not check_version((pending_pkg.version,
                                               pending_pkg.release),
                                              operator,
                                              (reqversion, reqrelease)):
                            # Pending package version does not suffice.
                            # We must skip this package to avoid dependency
                            # problems.
                            raise conflict_error, \
                                  'Conflicting packages: %s, %s' %\
                                  (pending.name, this_package.name)

                    # Merge packages in same transaction.
                    if not trans.id == pending_trans.id:
                        self.transactions.merge(trans.id, pending_trans.id)


                # The package was not in any pending transactions.  We
                # must add the package to the transaction.
                elif install_flag in [INSTALL, UPGRADE]:
                    pkgdata = self.get_package_data(requri)
                    pkgdata["flag"] = install_flag
                    name = pkgdata["name"]
                    group = pkgdata["group"]
                    newpackage = self.make_package(pkgdata)
                    trans.add(newpackage)
                    
                else:
                    # We should never get here. This means the install_flag
                    # is illegal.
                    raise Error, \
                          "Illegal install flags for package %s: '%s'" % \
                          (reqname, install_flag)

            else:
                pkg.resolved = true
                pkg = trans.next_unresolved()


    def check_conflicts_in_set(self, id):
        trans = self.transactions[id]
        if trans.has_conflicts():
            return true
        else:
            return false


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


    def _has_local_conflict_with_new(self, package):
        local_packages = self.driver.check_for_conflict(package.name,
                                                         package.version)
        for local_package in local_packages:
            if not self.transactions.find_package(local_package):
                return true

        # If we get here, conflicts specified by local packages will not
        # be a problem.
        return false


    def _has_new_conflict_with_local(self, package):
        if package.conflicts:
            for conflict in package.conflicts:
                if self.transactions.find_package(conflict.name):
                    continue
                if not conflict.flag:
                    if self.driver.query_by_name(conflict.name):
                        return true
                else:
                    local_matches = self.driver.query_by_name(conflict.name)
                    if local_matches:
                        for local_match in local_matches:
                            local_version = local_match[0]
                            if _check_conflict_versions(local_version,
                                                         flag,
                                                         conflict.version):
                                return true

            # If we get here, conflicts specified by new packages will not
            # be a proble.
            return false
                        

    def check_local_conflicts(self):
        ids = self.transactions.keys()
        deleted_ids = []
        for id in ids:
            if id in deleted_ids: continue
            for package in self.transactions[id].members():

                # Checking if local packages report trouble.
                if self._has_local_conflict_with_new(package):
                    skipped = self.transactions[id].keys()
                    skipped = string.join(skipped, " ")
                    message = "New package has conflict with installed"\
                              " packages: %s.\n"\
                              "Skipping packages: %s"\
                              % (package.name, skipped)
                    self.log.write_stderr(message)
                    self.transactions.remove(id)
                    deleted_ids.append(id)
                    break
                
                # Checking if new packages report trouble with local ones.
                elif self._has_new_conflict_with_local(package):
                    skipped = self.transactions[id].keys()
                    skipped = string.join(skipped, " ")
                    message = "New package has conflict with installed"\
                              " packages: %s.\n"\
                              "Skipping packages: %s"\
                              % (package.name, skipped)
                    self.log.write_stderr(message)
                    self.transactions.remove(id)
                    deleted_ids.append(id)
                    break

        
    def check_conflicts(self):
        # Check for conflicts within a transaction.
        for id in self.transactions.keys():
            if self.check_conflicts_in_set(id):
                skipped = string.join(trans.keys(), " ")
                self.transactions.remove(trans.id)
                message = "Transaction set has conflicts.\n"\
                          "Skipping packages: %s" % skipped
                self.log.write_stderr(message)
                self.log.write_log(message)

        # Check for conflicts between transactions.
        delete_ids = self.check_conflicts_between_sets()
        if delete_ids:
            skipped = ""
            for id in delete_ids:
                skipped = skipped + " " + \
                          string.join(self.transactions[id].keys(), " ")
                self.transactions.remove(id)
                message = "Packages skipped due to conflicts with other"\
                          " new packages:%s" % skipped
                self.log.write_log(message)
                self.log.write_stderr(message)

        # Check if local system report conflicts. If one is found, check if
        # conflicting local package will be upgraded - that will solve it.
        # Second, check if new package reports conflict with installed
        # package.
        self.check_local_conflicts()
        

    def solve_deps(self, packages):
        if not packages: raise error, "Empty argument for packagelist."
        self.init_packages(packages)

        trans = self.transactions.get_next_resolve()
        while trans:
            n_transactions = len(self.transactions)
            self.log.write_tty("\rResolving transactions"\
                                + 49*' ' + "(%-3i/%-3i)" %\
                                (trans.id+1, n_transactions))
            try:
                self.resolve(trans)
            except conflict_error, errmsg:
                skipped = string.join(trans.keys(), " ")
                self.transactions.remove(trans.id)
                message = "%s\nSkipping packages: %s." % (errmsg, skipped)
                self.log.write_stderr(message)
                self.log.write_log(message)
            except config_exclude_error, errmsg:
                skipped = string.join(trans.keys(), " ")
                self.transactions.remove(trans.id)
                message = "%s\nSkipping packages: %s." % (errmsg, skipped)
                self.log.write_stderr(message)
                self.log.write_log(message)
            except resolve_error:
                skipped = string.join(trans.keys(), " ")
                self.transactions.remove(trans.id)
                message = "Failed to resolve. Skipping packages: %s."\
                               % skipped
                self.log.write_stderr(message)
                self.log.write_log(message)
            trans = self.transactions.get_next_resolve()
        self.log.write_tty("\rChecking conflicts - ")
        self.check_conflicts()
        self.log.write_tty("\r"+ 80*' '+ "\rChecking conflicts - done.\n")
        #lists = self.transactions.get_lists()
        #return lists
        return self.transactions
                

            







