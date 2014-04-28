# -*- python -*-
# $Id: upgrade.py,v 1.19 2001/06/12 11:42:14 olafb Exp $

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

true, false = 1, 0

DEBUG = true

INSTALL_FLAG = "install"
UPGRADE_FLAG = "upgrade"

DEPENDENCY_ERROR_MESSAGE = \
"""There were some problems with dependencies when upgrading or
installing.  Usually problems arise when an upgrade will break already
installed software. In order to upgrade the selected package(s), you
must also upgrade the already installed (and depending) packages. A
'swup --upgrade' will usually fix this."""

NOSITES_ERROR_MESSAGE = \
"""Unable to open a site or get valid upgrade information. This will
happen if all top priority sites are down, or if upgrade information
is not available or is missing a valid signature from a known public
key. Check site, configuration and public keyring."""

# exceptions
class UpgradeException(Exception):
    def __init__(self, value=None):
        self.value = value
    def __str__(self):
        return str(self.value)

class DownloadException(UpgradeException): pass
class ResolveException(UpgradeException): pass
class FlushCacheException(UpgradeException): pass
class ParseException(UpgradeException): pass
class AuthException(DownloadException): pass

import sys, re, os, string
import spiparser, download, log
import resolver
import utils

is_uri_regexp = re.compile( "(.rdf)|(^http:)|(^ftp:)" )


def is_uri( uri ):
    if is_uri_regexp.search( uri ):
        return true
    else:
        return false


def _sort_2d_sitelist(element1, element2):
    pri1, pri2 = abs(int(element1[0])), abs(int(element2[0]))
    if  pri1 < pri2:
        return -1
    elif pri1 > pri2:
        return 1
    elif pri1 == pri2:
        return 0
    else:
        raise ValueError, "unable to compare"

def _compile_regexp(regexp):
    if regexp in [None, "", "None"]:
        return re.compile(".(?!.)")
    else:
        return re.compile(regexp)

    
def _compile_regexps(regexps):
    """Compile list of strings into regexp objects. Returns a list of
    re.RegexObject instances."""
    retlist = []
    for regexp in regexps:
        retlist.append(_compile_regexp(regexp))
    return retlist




class Package:
    "Class in which to store package information to send to resolver."
    def __init__(self, name):
        self.name = name
        self.uri = None
        self.flag = None
        self.signature_uri = None
        self.version = None
        self.release = None
        self.group = None




class Upgrade:
    "Base class for upgrade."


    def _init_driver(self):
        "Initialize package driver."
        drivername = self.config["driver"]
        try:
            exec "import %s; self.pkgdrv = %s.driver(self.log)" %\
                 (drivername, drivername)
        except ImportError:
            message = "Unable to load driver for packaging system."
            self.log.write_log(message)
            self.log.write_stderr(message)
            self.log.write_syslog_warning(message)
            raise UpgradeException, message


    def _init_log(self):
        "Initialize log."
        if string.lower(self.config["interactive_logged"]) == "yes":
            interactive_logged = true
        else:
            interactive_logged = false
        
        self.log = log.log(self.config["logfile"], self.config["loglevel"],
                           interactive_logged )


    def _init_reader(self):
        "Initialize RDF reader."
        self.reader = spiparser.rdf_reader()


    def _init_downloader(self):
        "Initialize downloader."
        try:
            self._downloader = download.download(
                self.log,
                self.config["cachedir"],
                self.config["tmpdir"])
        except download.DownloadException, err:
            raise UpgradeException, err

    def _init_regexps(self):
        "Initialize regular expressions for filter."
        regexps = _compile_regexps( [self.config["exclude_pkg_regexp"],
                                     self.config["include_pkg_regexp"],
                                     self.config["exclude_group_regexp"],
                                     self.config["include_group_regexp"]] )
        (self.exclude_pkg_regexp,
         self.include_pkg_regexp,
         self.exclude_group_regexp,
         self.include_group_regexp) = regexps

        
    def init(self):
        "Run initialization functions."
        self._init_log()
        self._init_driver()
        self._init_reader()
        self._init_regexps()
        self._init_downloader()
        self.latest = {}
        self.obsoletes = {}
        self.local_packages = {}
        

    def __init__(self, configdict=None):
        "Set up configuration and run initialization functions."
        if not configdict:
            import config
            self.config = config.parse()
        else:
            self.config = configdict
        self.init()
        

    def load_data(self, filename):
        'Load a serialized object from file. Return object.'
        import cPickle
        fd = open(filename)
        retval = cPickle.load(fd)
        fd.close()
        return retval


    def save_data(self, obj, filename):
        'Serialize and save a object obj to file given by filename.'
        import cPickle
        dirname = os.path.dirname(filename)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        fd = open(filename, 'w')
        cPickle.dump(obj, fd)
        fd.close()

        
    def retrieve_latest(self, uri):
        """Parse package list rdf, given the uri to the rdf-file.  Returns
        a dictionary with package name as key, and the a dictionary of
        name, version, release, summary, uri and obsoletes as value for
        keys."""
        # Check md5sum, pickle.load and/or dump -- to be implemented.

        # Get the md5sum uri:
        if uri[-3:] == '.gz':
            md5sum_uri = uri[:-3] + '.md5'
            noncompressed_uri = uri[:-3]
        else:
            noncompressed_uri = uri
            md5sum_uri = uri + '.md5'

        dict = None

        # Check if md5sum has changed. The check will update md5sums
        # if they are changed.
        if self.md5sum_isequal(md5sum_uri, noncompressed_uri):
            # Pickle already parsed latest-information.
            pickle_file = os.path.join(self.config['listsdir'], uri)
            pickle_file = utils.normalize_uri(pickle_file + '.pickle')
            if os.path.isfile(pickle_file):
                dict = self.load_data(pickle_file)
                
        if not dict:
            # Get latest, parse, and pickle-dump.
            local_filename = self.download_file(uri)
            (baseuri, basename) = os.path.split(uri)
            self.log.write_tty('\nParsing file: %s -' % basename)
            dict = self.reader.read_latest( local_filename, baseuri )
            self.log.write_tty('\rParsing file: %s - done\n' % basename)
            pickle_file = os.path.join(self.config['listsdir'], uri)
            pickle_file = utils.normalize_uri(pickle_file + '.pickle')
            self.save_data(dict, pickle_file)
        return dict


    def get_latest_lists(self):
        '''Returns a tuple of two dictionaries. The first dictionary is
        contains package information with package name as key, the second
        dictionary contains obsoletes information with package name to be
        obsoleted as key.'''
        if self.latest and self.obsoletes:
            return (self.latest, self.obsoletes)
        
        sitelist = self.config["sites"]
        sitelist.sort( _sort_2d_sitelist )
        pri_handled = []
        next_pri = 0

        main_latest = {}
        main_obsoletes = {}
        for site in sitelist:
            (pri, latest_uri, regexp) = site
            filter = _compile_regexp(regexp)
            pri = abs( int(pri) )
            if pri in pri_handled: continue
            elif pri > next_pri: break
            elif not filter:
                pri_handled.append( pri )
                continue
            try:
                message = "Fetching upgrade info '%s'" % latest_uri
                self.log.write_log( message )
                self.log.write_tty( '\r'+message )
                latest = self.retrieve_latest( latest_uri )
                for key in latest.keys():
                    if not filter.match(key):
                        del latest[key]
                obsoletes = self.find_who_obsoletes( latest )
            except (DownloadException, ParseException), errmsg:
                errmsg = "%s Skipping." % errmsg
                self.log.write_log( errmsg )
                self.log.write_stderr( errmsg ) 
                continue
            pri_handled.append( pri )
            next_pri = pri + 1
            # Update dictionary with information previously read.
            # Info read from sites with lower pri value will override
            # info from sites with higher pri value.
            latest.update(main_latest)
            obsoletes.update(main_obsoletes)
            main_latest = latest
            main_obsoletes = obsoletes

        self.latest = main_latest
        self.obsoletes = main_obsoletes
        return (self.latest, self.obsoletes)


    def get_local_info( self ):
        '''Get information about installed packages. Return a dictionary of
        installed packages in the format
        {<package_name>: [(<version>, <release>, <group>), (...)]}.'''
        if not self.local_packages:
            self.local_packages = self.pkgdrv.get_installed_pkgs()
        keys = self.local_packages.keys()
        return self.local_packages


    def get_info_by_uris( self, uris ):
        '''Given a list of package uris, return a list of package
        info dictionaries.'''
        info = []
        for uri in uris:
            try:
                (baseuri, basename) = os.path.split(uri)
                local_filename = self.download_file( uri )
                self.log.write_tty('\nParsing file: %s -' % baseuri)
                dict = self.reader.read_package_short( local_filename,
                                                       baseuri )
                self.log.write_tty('\rParsing file: %s - done' % baseuri)
                if dict:
                    info.append(dict)
            except spiparser.parse_error:
                raise ParseException, "Unable to parse file '%s'" % uri
        return info


    def get_info_by_names( self, names ):
        '''Given a list of package names, return a list of package
        info dictionaries.'''
        info = []
        latest, obsoletes = self.get_latest_lists()
        for name in names:
            if latest.has_key(name):
                package_info = latest[name]
            elif obsoletes.has_key(name):
                # Just pick the first package found that obsoletes.
                package_info = obsoletes[name][0]
            else:
                package_info = None
            info.append(package_info)
        return info


    def find_who_obsoletes( self, latestdict ):
        """Given a dictionary over latest packages, return a dictionary
        with obsoleted package as key and a list of packages that obsoletes
        the package as value for key."""
        obsoleted_by = {}
        for name in latestdict.keys():
            if latestdict[name]["obsoletes"]:
                for obs in latestdict[name]["obsoletes"]:
                    if not obsoleted_by.has_key(obs):
                        obsoleted_by[obs] = [name]
                    else:
                        obsoleted_by[obs].append(name)
        return obsoleted_by

        
    def regexp_filter( self, name, group ):
        """Filter (<name>, <group>) through regexps given in configuration
        file. Returns 1 if package is to be upgraded or installed, 0
        otherwise."""
        if self.exclude_pkg_regexp.match(name):
            return false
        elif self.include_pkg_regexp.match(name):
            return true
        elif self.exclude_group_regexp.match(group):
            return false
        elif self.include_group_regexp.match(group):
            return true

        
    def md5sum_isequal(self, md5sumuri, uri):
        '''Given an uri to a md5sum and an uri to the file. Check if the m
        d5sum has changed since last time the file was read. Record the new
        md5sum and return 0 if not equal and 1 if equal.'''
        old_md5s = {}
        new_md5s = {}
        md5sumfile = self.config["md5sumfile"]
        if os.path.isfile(md5sumfile):
            fd = open(md5sumfile)
            line = fd.readline()
            while line:
                split = string.split(line)
                if len(split) == 2:
                    md5, file = split
                    old_md5s[file] = md5
                line = fd.readline()
            fd.close()
        try:
            tmpfile = self.download_file(md5sumuri, CHECKSIG=0)
        except DownloadException, errmsg:
            return 0
        
        fd = open(tmpfile)
        line = fd.readline()
        while line:
            split = string.split(line)
            if len(split) == 2:
                md5, file = split
                file = os.path.join(os.path.dirname(uri), file)
                new_md5s[file] = md5
            line = fd.readline()
        fd.close()

        isequal = 0
        key = uri
        if old_md5s.has_key(key) and new_md5s.has_key(key):
            if new_md5s[key] == old_md5s[key]:
                isequal = 1

        # If the md5sum has changed, store new md5sums.
        if not isequal:
            old_md5s.update(new_md5s)
            md5sumdir = os.path.dirname(md5sumfile)
            if not os.path.isdir(md5sumdir):
                os.makedirs(md5sumdir)
            fd = open(md5sumfile, 'w')
            for key in old_md5s.keys():
                md5 = old_md5s[key]
                fd.write('%s  %s\n' % (md5, key))
            fd.close()
        return isequal

       
    def download_file(self, uri, siguri=None, CHECKSIG=1):
        "Download file from uri and check signature. Returns local filename."
        try:
            filename = self._downloader.download(uri, siguri, CHECKSIG)
            return filename
        except download.AuthException, errmsg:
            raise AuthException, errmsg
        except download.DownloadException, errmsg:
            raise DownloadException, errmsg

            
    def resolve_deps(self, packages):
        '''Resolve dependencies for the list of Package-instances, return a
        resolver.transactions instance.'''
        dep_resolver = resolver.resolver( self.reader, self.regexp_filter,
                                          self.pkgdrv, self.download_file,
                                          self.log )
        try:
            transactions = dep_resolver.solve_deps( packages )
            info = "" 
            for transaction in transactions.values():
                for package in transaction.values():
                    info = info + \
                           "\n\t%s: %s, version %s release %s" % \
                           (package.flag, package.name,
                            package.version, package.release)
            if info != "":
                message = "Packages to install/upgrade:%s" % info
                self.log.write_log(message)
                self.log.write_stdout(message)
        except (resolver.DependencyError, resolver.ParseError), errmsg:
            raise ResolveException, errmsg
        return transactions


    def flush_cache(self):
        'Flush cache if flush_cache option in configuration is set to "yes".'
        if string.lower(str(self.config["flush_cache"])) == "yes":
            try:
                self._downloader.flush_cache()
            except download.flush_cache_error, msg:
                raise FlushCacheException, msg


    def install(self, transaction):
        'Given a resolver.transactions instance, run the transactions.'
        try:
            self.pkgdrv.install(transaction)
            return None
        except self.pkgdrv.install_error, errmsg:
            return errmsg


    def create_resolver_input(self, packages, flag):
        '''Given a list of either package uris or package names and a flag
        specifying "install" or "upgrade", return input for the resolver.'''
        if not packages:
            return None
        
        resolver_input = []
        siguri = None
        if is_uri( packages[0] ):
            selected = self.get_info_by_uris( packages )
            for i in range(len(selected)):
                package_info = selected[i]
                if self.check_package( package_info ):
                    newpackage = Package(package_info["name"])
                    newpackage.uri = packages[i]
                    newpackage.flag = flag
                    newpackage.version = package_info["version"]
                    newpackage.release = package_info["release"]
                    resolver_input.append( newpackage )
        else :
            selected = self.get_info_by_names( packages )
	    if selected == None:
                self.log.write_log( NOSITES_ERROR_MESSAGE )
                self.log.write_stderr( NOSITES_ERROR_MESSAGE )
            else:
                for i in range( len(selected) ):
                    package_info = selected[i]
                    name = packages[i]
                    if not package_info:
                        message = "Nothing found for '%s'." % name
                        self.log.write_log( message )
                        self.log.write_stderr( message )
                        continue
                    
                    if self.check_package( package_info ):
                        newpackage = Package(package_info["name"])
                        newpackage.uri = package_info["uri"]
                        newpackage.flag = flag
                        newpackage.version = package_info["version"]
                        newpackage.release = package_info["release"]
                        resolver_input.append( newpackage )
        return resolver_input


    def _main( self, packages ):
        'Common main loop for upgrade or install.'
        if string.lower( str(self.config["poll_only"]) ) == "yes":
            message = "Found these packages:\n"
            for pkg in packages:
                message = message + "\t%s: %s-%s-%s\n" %\
                          (pkg.flag, pkg.name, pkg.version, pkg.release)
            message = message + "\tTotal %i packages." % len( packages )
            self.log.write_stdout(message)
            self.log.write_log(message)
        else:
            transactions = self.resolve_deps(packages)
            if not transactions:
                message = "Nothing to install or upgrade."
                self.log.write_stdout_info( message )
                self.log.write_log( message )
                return
            i = 0
            errorflag = false

            for key in transactions.keys():
                transaction = transactions[key]
                try:
                    for package in transaction.values():
                        uri = utils.normalize_uri(package.uri)
                        siguri = utils.normalize_uri(package.signature_uri)
                        package.localfilename = self.download_file(uri, siguri)
                except DownloadException, errmsg:
                    skipped = ""
                    for name in transaction.keys():
                        skipped = skipped + name + " "
                    skipped = string.rstrip( skipped )
                    errmsg = "%s\nSkipping packages %s" % (errmsg, skipped)
                    self.log.write_log( errmsg )
                    self.log.write_stderr( errmsg )
                    del transactions[key]
                    continue

                if self.config['save_to']:
                    todir = self.config['save_to']
                    import shutil
                    if not os.path.isdir( todir ):
                        message = 'Can not save copy of packages.'\
                                  ' No such directory'\
                                  ': %s' % todir
                        self.log.write_log( message )
                        self.log.write_stderr( message )
                    else:
                        for package in transaction.values():
                            try:
                                fromfile = package.localfilename
                                basename = os.path.basename( fromfile )
                                tofile = os.path.join( todir, basename )
                                shutil.copyfile( fromfile, tofile )
                            except IOError:
                                message = 'Unable to move file %s to %s' % \
                                          (fromfile, tofile)
                                self.log.write_stderr( message )
                                self.log.write_log( message )

                if not string.lower( str(self.config["download_only"]) ) == \
                   "yes":
                    errmsg = self.install( transaction )
                    if errmsg:
                        errorflag = true
                        self.log.write_log( errmsg )
                        self.log.write_stderr( errmsg )
                    else:
                        self.flush_cache()
                i = i +1
            self.log.write_tty( "\n" )
            if errorflag:
                self.log.write_stderr( DEPENDENCY_ERROR_MESSAGE )

                        
    def check_package( self, package ):
        '''Given a package info dictionary, return true if package is accepted
        for upgrade or install, return false if not. Function is used by
        create_resolver_input. Can be overloaded for install-purposes.'''
        if not package:
            return
        name = package["name"]
        uri = package["name"]
        version = package["version"]
        release = package["release"]

        # Check if package is a valid upgrade for an installed package.
        local_packages = self.get_local_info()
        if local_packages.has_key( name ):
            if len( local_packages[name] ) > 1:
                message = "Multiple versions installed." \
                          " Skipping package %s" % name
                self.log.write_stderr( message )
                self.log.write_log( message )
                return false
            for local_pkg in local_packages[name]:
                current_version, current_release = local_pkg[:2]
                comparison = utils.version_cmp( (version, release),
                                                (current_version,
                                                current_release) )
                if  comparison > 0:
                    return true
                elif comparison == 0:
                    #Package is already installed, notify the user,
                    #if all packages are already installed exit.
                    message = "Package %s" % name +\
                              " is already at newest version (%s-%s)."\
                              % (current_version, current_release)
                    self.log.write_log( message )
                    self.log.write_stderr( message )
                    return false

        # Check if package obsoletes an installed package, and should
        # therefore be set to upgrade.
        if package.has_key( "obsoletes" ):
            obsoletes = package["obsoletes"]
            for obs_name in obsoletes:
                if local_packages.has_key( obs_name ):
                    return true

        # Package is not an upgrade or obsoletes an installed package.
        return false
        

    def select_packages(self):
        'Returns a list of names of packages to upgrade.'
        local_packages = self.get_local_info()
        latest, obsoletes = self.get_latest_lists()
        selection = []
        for name in local_packages.keys():
            packages = local_packages[name]
            if not latest.has_key(name): continue
            # Do not touch packages that are multiply installed.
            if len(packages) > 1: continue
            version, release, group = packages[0]
            latest_package = latest[name]
            latest_version = latest_package["version"]
            latest_release = latest_package["release"]
            if self.regexp_filter(name, group):
                if utils.version_cmp( (latest_version, latest_release),
                                      (version, release)) > 0:
                    selection.append(name)
        return selection


    def main(self):
        'Main function called by run(). Can be overloaded.'
        # Main function. Can be subclassed.
        message = "Starting upgrade."
        self.log.write_log( message )
        self.log.write_stdout_verbose( message )
        selection = self.select_packages()
        packages = self.create_resolver_input(selection, UPGRADE_FLAG)
        if not packages:
            message = "Your system is up to date."
            self.log.write_log( message )
            self.log.write_stdout_info( message )
        else:
            self._main(packages)


    def run( self ):
        try:
            self.main()
            self.flush_cache()
        except UpgradeException, errmsg:
            message = str(errmsg)
            self.log.write_log( message )
            self.log.write_stderr( message )
            self.flush_cache()
            raise
        except KeyboardInterrupt:
            message = "User interrupt."
            self.log.write_log( message )
            self.log.write_stderr( "\n"+message )
            self.flush_cache()
            raise
        except:
            exception, errmsg = sys.exc_info()[:2]
            message = "Fatal error: [%s] %s." % (exception, errmsg)
            self.log.write_log( message )
            self.log.write_stderr( message )
            self.log.write_syslog_warning( message )
            self.flush_cache()
            raise UpgradeException, message



                
class upgrade_package( Upgrade ):


    def __init__( self, install_list, configdict = None ):
        Upgrade.__init__( self, configdict )
        self.install_list = install_list

    
    def check_package( self, package ):
        if not package:
            return
        name = package["name"]
        uri = package["name"]
        version = package["version"]
        release = package["release"]

        # Check if package is a valid upgrade for an installed package.
        local_packages = self.get_local_info()
        if local_packages.has_key( name ):
            if len( local_packages[name] ) > 1:
                message = "Multiple versions installed." \
                          " Skipping package %s" % name
                self.log.write_stderr( message )
                self.log.write_log( message )
                return false
            for local_pkg in local_packages[name]:
                current_version, current_release = local_pkg[:2]
                comparison = utils.version_cmp( (version, release),
                                                (current_version,
                                                current_release) )
                if  comparison > 0:
                    return true
                elif comparison == 0:
                    #Package is already installed, notify the user,
                    #if all packages are already installed exit.
                    message = "Package %s" % name +\
                              " is already at newest version (%s-%s)."\
                              % (current_version, current_release)
                    self.log.write_log( message )
                    self.log.write_stderr( message )
                    return false

        # Check if package obsoletes an installed package, and should
        # therefore be set to upgrade.
        if package.has_key( "obsoletes" ):
            obsoletes = package["obsoletes"]
            for obs_name in obsoletes:
                if local_packages.has_key( obs_name ):
                    return true

        # Package is not an upgrade or obsoletes an installed package.
        return false

    
    def main( self ):
        message = "Starting upgrade of package."
        self.log.write_log(message)
        self.log.write_stdout_verbose(message)
        packages = self.create_resolver_input(self.install_list,
                                              UPGRADE_FLAG)
        if packages:
            self._main(packages)
        self.flush_cache()



    
class install_package( Upgrade ):


    def __init__( self, install_list, configdict = None ):
        Upgrade.__init__( self, configdict )
        self.install_list = install_list


    def check_package( self, package ):
        if not package:
            return        
        name = package["name"]
        local_packages = self.get_local_info()
        if local_packages.has_key( name ):
            message = "Already installed package, try upgrading: %s" % name
            self.log.write_stderr( message )
            self.log.write_log( message )
            return false

        # Package is not installed. It is ok to install it.
        return true        


    def main( self ):
        message = "Starting install."
        self.log.write_log( message )
        self.log.write_stdout_verbose( message )
        packages = self.create_resolver_input(self.install_list,
                                              INSTALL_FLAG)
        if packages:
            self._main(packages)
        else:
            self.flush_cache()

        self.flush_cache()




class list_latest( Upgrade ):


    def __init__( self, configdict = None ):
        Upgrade.__init__(self, configdict)


    def write( self ):
        data, obsoletes = self.get_latest_lists()
        self.log.write_tty('\n')
        if not data: return
        keys = data.keys()
        keys.sort()
        for name in keys:
            version = data[name]["version"]
            release = data[name]["release"]
            uri = data[name]["uri"]
            summary = data[name]["summary"]
            message = "%s-%s-%s - %s" % ( name, version, release, summary )
            self.log.write_stdout( message )


    def main(self):
        self.write()
        self.flush_cache()



        
class list_new( list_latest ):

    
    def __init__( self, configdict=None ):
        list_latest.__init__( self, configdict )
        

    def write( self ):
        data, obsoletes = self.get_latest_lists()
        self.log.write_tty('\n')
        if not data: return
        keys = data.keys()
        keys.sort()
        installed_pkgs = self.pkgdrv.get_installed_pkgs()
        for name in keys:
            if self.pkgdrv.packages.has_key( name ): continue
            version = data[name]["version"]
            release = data[name]["release"]
            uri = data[name]["uri"]
            summary = data[name]["summary"]
            message = "%s-%s-%s - %s" % ( name, version, release, summary )
            self.log.write_stdout( message )




