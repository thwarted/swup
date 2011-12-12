# -*- python -*-
# $Id: upgrade.py,v 1.171 2005/08/11 09:17:00 christht Exp $

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

import sys, re, os, string, types, urlparse
import resolver
from swuplib.driver import pkgdriver
from swuplib import spiparser
from swuplib import download
from swuplib import log
from swuplib import utils
from swuplib import config
from swuplib import ex
from UserDict import UserDict
DEBUG = False

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


NoValidSiteFoundError = "No site with valid filelist found."



    

class Upgrade:
    "Base class for upgrade."

    def _init_log(self):
        "Initialize log."
        if string.lower(self.config["interactive_logged"]) == "yes":
            interactive_logged = True
        else:
            interactive_logged = False
        
        self.log = log.log(self.config["loglevel"], interactive_logged )

    def _init_driver(self):
        "Initialize driver."
        self.pkgdrv = pkgdriver.pkgdriver(self.config, self.log)

    def _init_reader(self):
        "Initialize RDF reader."
        self.reader = spiparser.rdf_reader()


    def _init_downloader(self):
        "Initialize downloader."
        try:
            self._downloader = download.download(
                self.config,
                self.config["gnupgdir"],
                self.log,
                self.config["cachedir"],
                self.config["tmpdir"])
        except ex.download_error, err:
            raise ex.upgrade_error, err
        except:
            raise


    def _init_regexps(self):
        "Initialize regular expressions for filter."
        regexps = self._compile_regexps( [self.config["exclude_pkg_regexp"],
                                     self.config["include_pkg_regexp"]])
        (self.exclude_pkg_regexp,
         self.include_pkg_regexp) = regexps

        
    def init(self):
        "Run initialization functions."
        self._init_log()
        self._init_driver()
        self._init_reader()
        self._init_regexps()
        self._init_downloader()
        

    def __init__(self, configdict=None):
        "Set up configuration and run initialization functions."
        if not configdict:
            self.config = config.parse()
        else:
            self.config = configdict
        self.init()
        self.latest = {}
        self.resources = {}
        self.obsoletes = {}
        self.obsoletors = {}
        self.emptylist = False
	self.removed_resource_providers = {}
    
    def _compile_wrapper(self, regexp):
        try:
            return re.compile(regexp)
        except Exception, e:
            message  = "Unable to compile regular expression: '%s'\n" %regexp
            message += "Error: %s\n" %e
            sys.stderr.write(message)
            sys.exit(1)
    
    def _compile_regexp(self, regexp):
        if regexp in [None, "", "None"]:
            return self._compile_wrapper("(?!.)")
        else:
            newre = ""
            if "+" in regexp:
                for char in regexp:
                    if char == "+":
                        newre += "\\+"
                    else:
                        newre += char
            else:
                newre = regexp
            return self._compile_wrapper(newre)

    
    def _compile_regexps(self, regexps):
        """Compile list of strings into regexp objects. Returns a list of
        re.RegexObject instances."""
        retlist = []
        for regexp in regexps:
            retlist.append(self._compile_regexp(regexp))
        return retlist


    def _sort_2d_sitelist(self, element1, element2):
        pri1, pri2 = abs(int(element1[0])), abs(int(element2[0]))
        if  pri1 < pri2:
            return -1
        elif pri1 > pri2:
            return 1
        elif pri1 == pri2:
            return 0
        else:
            raise ValueError, "unable to compare"


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


    def retrieve_latest(self, uri, get_resourcelist=False, get_resources=False):
        """Parse package list rdf, given the uri to the rdf-file.  Returns
        a dictionary with package name as key, and then a dictionary of
        name, version, release, summary, uri and obsoletes as value for
        keys.
        If resourcelist is True, then get the resourcelist rather than the
        latest list.
        If get_resources is True, get the resources."""

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
            #
            # Now we should remove rdfs for this site, as we need new ones:
            # But we don't want to flush the other lists
            # Lets use the Flush class for this:
            #
            baseuri, basename = os.path.split(uri)
            flusher = download.Flush(self.config)
            flusher.run(baseuri,flush_lists=False,flush_rpms=False)

            # Get latest, parse, and pickle-dump.
            #try to download gzipped file first
            try:
                local_filename = self.download_file(uri + '.gz', TYPE = 2)
            except ex.download_error, errmsg:
                local_filename = self.download_file(uri, TYPE = 2)
            except:
                raise
            
            self.log.write_tty('\nParsing file: %s -' % basename)
            if get_resourcelist:
                dict = self.reader.read_resourcelist(local_filename, baseuri)
            elif get_resources:
                dict = self.reader.read_resources(local_filename, baseuri)
            else:
                dict = self.reader.read_latest(local_filename, baseuri)
            self.log.write_tty('\rParsing file: %s - done\n' % basename)
            pickle_file = os.path.join(self.config['listsdir'], uri)
            pickle_file = utils.normalize_uri(pickle_file + '.pickle')
            self.save_data(dict, pickle_file)
            self.md5sum_set(md5sum_uri,noncompressed_uri)
            #
            # This makes the downloader behave:
            os.remove(local_filename)
            
        return dict


    def _find_obs( self, latestdict ):
        """Given a dictionary over latest packages. 
        Updates self.obsoletes and self.obsoletors
        Used by _generate_latest_lists
        """
        self.obsoletes = {}
        self.obsoletors = {}
        for name in latestdict.keys():
            if latestdict[name]["obsoletes"]:
                for obs in latestdict[name]["obsoletes"]:
                    if not self.obsoletes.has_key(obs):
                        self.obsoletes[obs] = [name]
                    else:
                        self.obsoletes[obs].append(name)
                    if not self.obsoletors.has_key(name):
                        self.obsoletors[name] = [obs]
                    else:
                        self.obsoletors[name].append(obs)

    def _latest_merge( self, main_latest, latest):
        '''Given two dictionaries, merge the packages into the first, and 
        return it'''
        for name in latest.keys():
            if not main_latest.has_key(name):
                main_latest[name] = latest[name]
                continue
	    #
	    # Package already exists, let's check what package to use:
	    #
            result = self.pkgdrv.version_compare(main_latest[name],latest[name])
            if result < 0:
	        #
		# package in latest is newer than package in main_latest:
		#
                main_latest[name] = latest[name]
		self.removed_resource_providers[main_latest[name]['uri']] = True
	    else:
	        #
		# package in main_latest is newer than package in latest:
		#
	        self.removed_resource_providers[latest[name]['uri']] = True
                
        
        return main_latest

    def _generate_latest_lists(self):
        '''Updates the latest, obsoletes and obsoletors dicts if needed.'''
        #
        # We only check latest. Maybe there are no obsoletes or obsoletors at
        # all.
        if not self.latest:

            #
            # Get list of sites:
            #
            sitelist = self.config["sites"]
            #
            # place sites in a list, and the list in a dict with class as key:
            #
            classlist = {}
            for site in sitelist:
                (pri, latest_uri, regexp, name, enabled) = site
                if not classlist.has_key(pri):
                    classlist[pri] = []
                classlist[pri].append((latest_uri, regexp, name, enabled))

            #
            # Now merge all sites belonging to one class into one latest dict:
            #
            latestlist = []
            prilist = classlist.keys()
            prilist.sort()
            prilist.reverse()
            valid_sitelist = []
            for pri in prilist:
                #
                # Get latest
                #
                sitelist = classlist[pri]
                
                main_latest = {}
                found_valid_site = 0
                for site in sitelist:
                    (latest_uri, regexp, name, enabled) = site
                    filter = self._compile_regexp(regexp)
                    if not filter or not enabled:
                        continue
                    if not latest_uri[-10:] == 'latest.rdf':
                        latest_uri = os.path.join(latest_uri, 'latest.rdf')
                        
                    try:
                        if name:
                            message = "Fetching upgrade info for site: %s" %name
                        else:
                            message = "Fetching upgrade info: '%s'" %latest_uri
                        self.log.write_syslog_info( message )
                        self.log.write_tty( "\r%s\n" %message )
                        latest = self.retrieve_latest( latest_uri )
                        for key in latest.keys():
                            if not filter.match(key):
                                del latest[key]
                        if pri == 0:
                            found_valid_site = 1
                        fullsite = (pri,latest_uri, regexp, name, enabled)
                        valid_sitelist.append(fullsite)
                    except (ex.download_error, ex.parse_error, ex.signature_error), errmsg:
                        errmsg = "%s\n" % errmsg + "Skipping '%s'" %latest_uri
                        self.log.write_syslog_err( message )
                        self.log.write_stderr( errmsg ) 
                        continue
                    except:
                        raise
                    #
                    # Here we merge the parsed list with earier lists of same
                    # class:
                    #
                    self._latest_merge(main_latest, latest)
                
                if pri == 0 and not found_valid_site == 1:
                    #
                    # we cannot live without a valid main site:
                    #
                    self.log.write_syslog_err(NoValidSiteFoundError)
                    self.log.write_stderr("\n%s" %NoValidSiteFoundError)
                    sys.exit(1)
                
                latestlist.append(main_latest)

            #
            # Merge all the class-specific latest dicts into the main systems
            # latest dict. This is easy, as they are already sorted:
            #
            for dict in latestlist:
                self.latest.update(dict)

            self._find_obs(self.latest)
            valid_sitelist.sort()
            self.config["sites"] = valid_sitelist


    def _get_resource_providers(self, resource):
        resourceinfo = []
        if self.resources.has_key(resource):
            item = self.resources[resource]
            if not type(item) == types.ListType:
                #
                # Old style: Info is found in separate rdf.
                #
                uri = item
                protocol, server, path = urlparse.urlparse(uri)[:3]
                if not (protocol and server):
                   path = os.path.join('../..', path)
                   baseuri = os.path.dirname(path)
                else:
                   baseuri = os.path.dirname(uri)
                filename = self.download_file(uri, TYPE=2)
                    
                resourceinfo = self.reader.read_resource(\
                    filename, baseuri)
            else:
                #
                # New style: info was part of resource.rdf
                #
                resourceinfo = item
        return resourceinfo

    def _generate_resources(self):
        self.resources = {}
        sitelist = self.config['sites']
        sitelist.sort()
        urilist = {}
        for site in sitelist:
            (pri,uri,regexp,name,enabled) = site
            if not enabled:
                continue
            baseuri, basename = os.path.split(uri)
            if not urilist.has_key(pri):
                urilist[pri] = [(baseuri, name)]
            else:
                urilist[pri].append((baseuri, name))
            

        for pri, prilist in urilist.items():
            pri_resources = {}
            for resourceuri, name in prilist:
                if name:
                    message = "Fetching resource info for site: %s" %name
                else:
                    message = "Fetching resource info: '%s'" %resourceuri
                self.log.write_syslog_info( message )
                self.log.write_tty( "\r%s\n" %message )
                resourcedata = {}
                try:
                    resuri = os.path.join(resourceuri,'resources.rdf')
                    resourcedata = self.retrieve_latest(resuri, \
                                            get_resources=True)
                except ex.download_error, error_one:
                    try:
                        resuri = os.path.join(resourceuri,'resourcelist.rdf')
                        resourcedata = self.retrieve_latest(resuri, 
                                                        get_resourcelist=True)
                    except ex.download_error, error_two:
                        #
                        # This means that neither the new or old file was found
                        #
                        message  = "%s\n" %string.strip("%s"%error_one)
                        message += "%s\n" %string.strip("%s"%error_two)
                        message += "Could not get remote resource " \
                                    +"information.\n"
                        if name:
                            message += "Skipping %s\n" %name
                        else:
                            message += "Skipping %s\n" %resourceuri
                        self.log.write_stderr( message )
                        self.log.write_syslog_err( message )

                for resname, provider in resourcedata.items():
                    if pri_resources.has_key(resname):
		        #
			# This resource already has one or more providers
			#
                        item = pri_resources[resname]
                        if not type(item) == types.ListType:
                            #
                            # Old style repos with this resource available was
                            # parsed _before_ the current one.
                            # That repos and resource/uri takes precedence.
                            #
                            continue
                        if not type(provider) == types.ListType:
                            #
                            # The current repos is old style and cannot be used
                            # to extend the list of resource providers.  A list
                            # of resource providers is already added from a
                            # site with better or equal class.  Nothing to do.
                            #
                            continue
			#
			# Extend the list of providers with the current one.
			#
			filtered_providers = []
			for pro in provider:
			    if self.removed_resource_providers.has_key(pro['uri']):
			        continue
		            else:
			        filtered_providers.append(pro)
			provider = filtered_providers
                        pri_resources[resname].extend(provider)
                    else:
                        pri_resources[resname] = provider
                    
            for resname, provider in pri_resources.items():
                if self.resources.has_key(resname):
                    #
                    # This resource is provided by one or more packages in
                    # a more important class repos. That one takes precendence.
                    #
                    continue
                else:
                    self.resources[resname] = provider

    def regexp_filter( self, name ):
        """Filter <name> through regexps given in configuration
        file. Returns 1 if package is to be upgraded or installed, 0
        otherwise."""
        if string.lower( str(self.config["ignore_filter"]) ) == "yes":
            return True
        if self.exclude_pkg_regexp.match(name):
            return False
        elif self.include_pkg_regexp.match(name):
            return True

        
    def md5sum_isequal(self, md5sumuri, uri):
        '''Given an uri to a md5sum and an uri to the file. Check if 
        the md5sum has changed since last time the file was read.
        Record the new md5sum and return 0 if not equal and 1 if equal.'''
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
            tmpfile = self.download_file(md5sumuri, CHECKSIG=0, TYPE=2)
        except ex.download_error, errmsg:
            return False
        except:
            raise
        
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

        # Delete downloaded md5sum file, this lets us not flush rdfs!
        os.remove(tmpfile)
        
        return isequal

    def md5sum_set(self, md5sumuri, uri):
        '''Given an uri to a md5sum and an uri to the file. Update
        the md5sum in the file with info from the uri.'''
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
            tmpfile = self.download_file(md5sumuri, CHECKSIG=0, TYPE=2)
        except ex.download_error, errmsg:
            return False
        except:
            raise
        
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

        # If the md5sum has changed, store new md5sums.
        old_md5s.update(new_md5s)
        md5sumdir = os.path.dirname(md5sumfile)
        if not os.path.isdir(md5sumdir):
            os.makedirs(md5sumdir)
        fd = open(md5sumfile, 'w')
        for key in old_md5s.keys():
            md5 = old_md5s[key]
            fd.write('%s  %s\n' % (md5, key))
        fd.close()
        
        # Delete downloaded md5sum file, this lets us not flush rdfs!
        os.remove(tmpfile)
        
        return True
       
    def download_file(self, uri, siguri=None, CHECKSIG=1, TYPE=1):
        "Download file from uri and check signature. Returns local filename."
        "TYPE is: 1 = rpm-related, 2 = rdf-related"
        try:
            filename = self._downloader.download(uri, siguri, CHECKSIG, TYPE)
        except ex.download_error, errmsg:
            raise ex.download_error, errmsg
        return filename

    def resolve_deps(self, packages):
        '''Resolve dependencies for the list of Package-instances, return a
        resolver.transactions instance.'''
        result = 0
        dep_resolver = resolver.resolver( self.reader, self.regexp_filter,
                                          self.pkgdrv, self.download_file,
                                          self.log, self.config, 
                                          self.latest, self.emptylist,
                                          self.resources)
        try:
            transactions, swupgrade = dep_resolver.solve_deps( packages , 
                                                    self.obsoletors)
            info = "" 

            for transaction in transactions.values():
                for package in transaction.values():
                    info += \
                           "\n\t%s: %s, version %s release %s" % \
                           (package['flag'], package['name'],
                            package['version'], package['release'])
            if info != "":
                message = "Packages to install/upgrade:%s" % info
                
                # This clutters the log, we get the info from other sources.
                #self.log.write_syslog_info( message )
                self.log.write_stdout(message)
        except ex.empty_package_list_error, errmsg:
            raise ex.empty_package_list_error, errmsg
        except ex.coder_messed_up_error, errmsg:
            raise ex.coder_messed_up_error, errmsg
        except:
            raise
        return transactions, result


    def _check_package(self, flag, package, input_names):
        '''Given a package info dictionary, and the flag, return True if 
           package is accepted for install / upgrade, return False if not.
           Also return the flag, which might have been modified.'''
        if not package:
            return False, flag
        
        name = package['name']
        
        #
        # Get status of package:
        #

        status = self.pkgdrv.is_installed(package)
        #
        # Check if package is a valid upgrade:
        #
        if status == -2 and flag == UPGRADE_FLAG:
            #
            # Package is not installed, and we asked for upgrade, maybe we 
            # still 
            # need to install this package...
            #
            # Check if package obsoletes an installed package, and should
            # therefore be set to upgrade.
            #
            if package.has_key( "obsoletes" ):
                obsoletes = package["obsoletes"]
                for obs_name in obsoletes:
                    if self.pkgdrv.is_installed(obs_name) > -2:
                        message = "Package '%s' obsoletes " %name \
                                    +"installed package '%s'" \
                                    %obs_name
                        self.log.write_syslog_err(message)
                        self.log.write_stderr(message) 
                        if not self.regexp_filter(name):
                            message = "Package '%s' skipped due to " %name\
                                        +"config rule."
                            self.log.write_syslog_err(message)
                            self.log.write_stderr(message) 
                        else:
                            return True, flag
                #
                # None of the obsoletors was approved, let's give up:
                #
                if not self.emptylist:
                    message = "Package '%s' is not installed." %package['name']
                    self.log.write_syslog_err(message)
                    self.log.write_stderr("\n" +message) 
                return False, flag
            #
            # We don't want to automaticly install this package. It's up
            # to the user.
            #
            if not self.emptylist:
                message = "Package '%s' is not installed." %package['name']
                self.log.write_syslog_err(message)
                self.log.write_stderr("\n" +message) 
            return False, flag
        
        if status <= 0 and flag == UPGRADE_FLAG:
            #
            # Package is already installed with better or equal version as the 
            # potential upgrade. No need to perform upgrade.
            # 
            real_input = False
            for pkg in input_names:
                if pkg == name:
                    real_input = True
                    
            if not self.emptylist or real_input:
                message = "Package '%s' is already " %package['name']\
                            +"newest version."                 
                self.log.write_syslog_err(message)
                self.log.write_stderr(message) 
            return False, flag
            
        if status == 1 and flag == UPGRADE_FLAG:
            #
            # Installed package lesser than the potential upgrade
            # Let's check if there are more than one installed package:
            #
            
            installed = self.pkgdrv.get_packages(name)
            if len(installed) > 1:
                for instpackage in installed:
                    if self.pkgdrv.version_compare(instpackage, package) >= 0:
                        #
                        # Already installed a just as good package. Dont 
                        # perform upgrade:
                        #
                        return False, flag
            
            if not self.regexp_filter(name):
                message = "Package '%s' skipped due to config rule." %name
                self.log.write_syslog_err(message)
                self.log.write_stderr(message) 
                return False, flag

            # 
            # Now check for obsoletes, just to notify the user:
            #
            if package.has_key( "obsoletes" ):
                obsoletes = package["obsoletes"]
                for obs_name in obsoletes:
                    if self.pkgdrv.is_installed(obs_name) > -2:
                        message = "Package '%s' obsoletes " %name \
                                    +"installed package '%s'" \
                                    %obs_name
                        self.log.write_syslog_err(message)
                        self.log.write_stderr(message) 
            return True, flag
            
            
        #
        # Check if package is a valid install:
        #
        if status == -2 and flag == INSTALL_FLAG:
            #
            # Package is not installed, go ahead with installation
            #
            if not self.regexp_filter(name):
                message = "Package '%s' skipped due to config rule." %name
                self.log.write_syslog_err(message)
                self.log.write_stderr(message) 
                return False, flag
            #
            # Check for obsoletes, if found modify flag and notify user:
            #
            if package.has_key( "obsoletes" ):
                obsoletes = package["obsoletes"]
                for obs_name in obsoletes:
                    if self.pkgdrv.is_installed(obs_name) > -2:
                        message = "Package '%s' obsoletes " %name \
                                    +"installed package '%s'" \
                                    %obs_name
                        self.log.write_syslog_err(message)
                        self.log.write_stderr(message) 
                        flag = UPGRADE_FLAG
            return True, flag
            
        if status == 1 and flag == INSTALL_FLAG:
            #
            # Package is installed but lesser than potential installation,
            # should notify the user about this status, so that we can try an
            # upgrade instead. 
            #
            if not self.regexp_filter(name):
                message = "Package '%s' skipped due to config rule." %name
                self.log.write_syslog_err(message)
                self.log.write_stderr(message) 
                return False, flag
            message = "Package '%s' is installed, but potential upgrade " \
	    		%package['name'] +"was found. "  \
                        +"Upgrading."
            flag = UPGRADE_FLAG
            #
            #  Check if package obsoletes installed package and notify the user.
            #
            if package.has_key( "obsoletes" ):
                obsoletes = package["obsoletes"]
                for obs_name in obsoletes:
                    if self.pkgdrv.is_installed(obs_name) > -2:
                        message = "Package '%s' obsoletes " %name \
                                    +"installed package '%s'" \
                                    %obs_name
                        self.log.write_syslog_err(message)
                        self.log.write_stderr(message) 
            self.log.write_syslog_err(message)
            self.log.write_stderr(message) 
            return True, flag
            
        if status <= 0 and flag == INSTALL_FLAG:
            #
            # Package is installed and just as good as the potential 
            # installation.
            # No need to perform this installation:
            #
            real_input = False
            for pkg in input_names:
                if pkg == name:
                    real_input = True
                    
            if not self.emptylist or real_input:
                message = "Package '%s' is already newest version." \
                                                        %package['name']
                self.log.write_syslog_err(message)
                self.log.write_stderr(message) 
            return False, flag
        
        #
        # Don't think it's even possible to get here, but:
        #
        message = "This should never happen."
        self.log.write_syslog_err(message)
        self.log.write_stderr(message)
        return False, flag
        

    def _match_packages( self, regexps, flag):
        matches = {}
        self.installed = {}
        if flag == UPGRADE_FLAG:
            self.installed = self.pkgdrv.get_installed()
        #
        # This is not optimal speed wise, but it's the logical way:
        #
        for regexp in regexps:
            reg = self._compile_regexp("%s$" %regexp)
            if flag == UPGRADE_FLAG:
                matched = False
                #
                # For upgrade we only check the local database.
                #
                for key in self.installed.keys():
                    if matches.has_key(key):
                        matched = True
                    elif re.match(reg, key):
                        matches[key] = True
                        matched = True
                if not matched:
                    message = "Nothing found for '%s'" %regexp
                    self.log.write_stdout(message)
            else:
                #
                # For install we first check latest, if not matched
                # we check obsoletes.
                #
                matched = False
                for key in self.latest.keys():
                    if matches.has_key(key):
                        matched = True
                        
                    elif re.match(reg, key):
                        matches[key] = True
                        matched = True
                if not matched:
                    for key in self.obsoletes.keys():
                        if matches.has_key(key):
                            matched = True
                        elif re.match(reg, key):
                            matches[key] = True
                            matched = True
                if not matched:
                    message = "Nothing found for '%s'\n" %regexp
                    self.log.write_stdout(message)
        return matches.keys()

    def parse_input( self, packages, flag):
        '''Given a list of package names, make sure the content is valid, 
           modify if not, and return the updated list, and information
           about noexistant packages (if needed).'''
        info = []
        none_warns = []
        package_name = None
        
        #
        # If we are going to upgrade, and we got no packages as input, 
        # lets try all:
        #
        if len(packages) == 0:
            #
            # Don't tell folks about all the newest versions... :)
            #
            self.emptylist = True
            installed = self.pkgdrv.get_installed()
            for key in installed.keys():
                if self.obsoletes.has_key(key):
                    #
                    # one or more packages may obsolete it, let's try to be
                    # intelligent. If an obsoletor already is installed, we
                    # should use that one. If none is, let's take the first
                    # available.
                    #
                    picked = False
                    obsoletor = ""
                    for obsoletor in self.obsoletes[key]:
                        if installed.has_key(obsoletor):
                            info.append(obsoletor)
                            picked = True
                    if not picked:
                        obsoletor = self.obsoletes[key][0]
                        info.append(obsoletor)
                elif self.latest.has_key(key):
                    info.append(key)
                #
                # an installed package can be amongst the obsoleted packages
                # too, let's check:
                #
                            
        else:
            
            #
            # This is either install or upgrade with package arguments.
            #
            
            #
            # Lets do some regexp matching:
            #
            packages = self._match_packages(packages, flag)
        
            
            #
            # Now let's check the input given:
            #
            for name in packages:
                if self.latest.has_key(name):
                    package_name = name
                elif self.obsoletes.has_key(name):
                    #
                    # Package is obsoleted, check if one of the obsoletors is 
                    # installed or use the first one instead of the obsoleted 
                    # package:
                    #
                    message = ""
                    installed = False
                    alternative_obsoletors = []
                    #
                    # Find all possible obsoletors:
                    #
                    for obsoletor in self.obsoletors.keys():
                        for package in self.obsoletors[obsoletor]:
                            if package == name:
                                alternative_obsoletors.append(obsoletor)
                    #
                    # Try to pick one intelligently. We prefer if the 
                    # obsoletor is already installed. (Not likely but can 
                    # happen if packages have merged)
                    #
                    for obsoletor in alternative_obsoletors:
                        if self.pkgdrv.is_installed(obsoletor) == 2:
                            installed = True
                            package_name = obsoletor
                            continue
                    #
                    # No luck, pick the first available obsoletor, since we 
                    # have at least 1
                    #
                    if not installed:
                        package_name = alternative_obsoletors[0]
                else:
                    package_name = None
                    none_warns.append("Nothing found for '%s'" %name)
                #
                # Only append package name if not None
                #
                if package_name:
                    info.append(package_name)

        return info, none_warns

        


    def create_resolver_input(self, package_names, flag):
        '''Given a list of package names and a flag
        specifying "install" or "upgrade", return a tuple of input for the 
        resolver, and dict with obsoletors as keys, and a list of 
        obsoleted packages as values.'''
        
        self._generate_latest_lists()
        self._generate_resources()
        resolver_input = []
        siguri = None
        
        
        message = "Verifying packages."
        self.log.write_stdout_info( message )

        packages, none_warns = \
           self.parse_input(package_names, flag)
        

        #
        # Change from package names to package dicts:
        #
        dicts = []
        for package in packages:
            if self.latest.has_key(package):
                dicts.append(self.latest[package])
        packages = dicts
        #
        # Now lets check the packages
        #
        for package in packages:
            result, newflag = self._check_package( flag, package, package_names)
            if result:
                #
                # add some needed items:
                #
                package['signature_uri'] = "%s.asc" %package['uri']
                package['flag'] = newflag
                package['resolved'] = False
                resolver_input.append( package )

        self.log.write_stdout_info( "Done verifying packages.")

        #
        # User information about nonexistant packages:
        #
        if len(none_warns) > 0:
            message = ""
            for i in range( len(none_warns)):
                message += none_warns[i] + "\n"
            self.log.write_syslog_err( message )
            self.log.write_stderr( message )
        
        return resolver_input
    
    
    def install(self, transaction):
        '''Given a resolver.transactions instance, run the transactions.'''
        try:
            self.pkgdrv.opendb_readwrite()
            self.pkgdrv.install(transaction)
        except ex.install_error, inste:
            errmsg = inste.value1 + "\n"
            progress = "StartTranactionError\nStartHeader\n%s" \
                %errmsg
            progress += "StopHeader\nStartPackages\n"
            for name in inste.value2:
                progress += "Failed %s\n" %name
                errmsg += "Skipping %s\n" %name
            progress += "StopPackages\nStopTransactionError\n"
            self.log.write_progress(progress)
            self.log.write_stderr(errmsg)
            return errmsg

    def _main( self, packages ):
        'Common main loop for upgrade or install.'

        transactions = None
        swupgrade = False
        if self.config["stage"]:
            #
            # load resolved pickle if found
            #
            pickle_file = \
                os.path.join(self.config['cachedir'], self.config['resolved'])
            if os.path.isfile(pickle_file):
                (transactions, swupgrade) 
                dict = self.load_data(pickle_file)
                transactions = dict['transactions']
                swupgrade = dict['swupgrade']
        if not transactions:
            transactions, swupgrade = self.resolve_deps(packages)
        if transactions and self.config["stage"]:
            #
            # Transactions is not objects we can serialize, but we only use
            # them as dicts from this point on...
            #
            try:
                dict = {}
                for transkey in transactions.keys():
                    trans = transactions[transkey]
                    tmpdict = {}
                    for tkey in trans.keys():
                        tmpdict[tkey] = trans[tkey]
                    dict[transkey] = tmpdict
                newdict = {'transactions': dict,'swupgrade': swupgrade}
                self.save_data(newdict, pickle_file)
            except:
                raise
        if not transactions:
            message = "Nothing to install or upgrade."
            self.log.write_stdout_info( message )
            self.log.write_syslog_info( message )
            return
        if string.lower( str(self.config["poll_only"]) ) == "yes":
            message = "Found these packages:\n"
            i = 0
            for transaction in transactions.values():
                for pkg in transaction.values():
                    i = i + 1
                    message = message + "\t%s: %s-%s-%s\n" %\
                          (pkg['flag'], pkg['name'], 
                            pkg['version'], pkg['release'])
                message = message + "\n"
            message = message + "\tTotal %i packages." %i
            self.log.write_stdout(message)
            self.log.write_syslog_info( message )
        else:
            self.config['prog_total'] = 0
            for key, transaction in transactions.items():
                numpkgs = len(transaction)
                self.config['prog_total'] += numpkgs
                    
            i = 0
            for key in transactions.keys():
                errorflag = False
                transaction = transactions[key]
                skipped = ""
                for package in transaction.values():
                    try:
                        self.log.write_tty('\rDownloading %s ' \
                                            % package['name'])
                        uri = utils.normalize_uri(package['uri'])
                        siguri = utils.normalize_uri(package['signature'])
                        package['localfilename'] = \
                            self.download_file(uri, siguri)
                        self.log.write_tty(\
                            '\rDownloading %s - done' % package['name']\
                            +(61-len(package['name']))*' '+'\n')
                    
                    except ex.download_error, errmsg:
                        progress = "Skipping %s %s" \
                            %(package['name'], self.config['prog_total'])
                        self.log.write_progress(progress)
                        errorflag = True
                        for name in transaction.keys():
                            skipped = skipped + name + " "
                        skipped = string.rstrip( skipped )
                        if not self.config['stage']:
                            break
                    except:
                        raise

                if errorflag and not self.config['stage']:
                    errmsg = "%s\nSkipping packages %s" % (errmsg, skipped)
                    self.log.write_syslog_err( errmsg )
                    self.log.write_stderr( errmsg )
                    #del transaction[package["name"]]
                    del transactions[key]
                    
                if self.config['save_to']:
                    todir = self.config['save_to']
                    import shutil
                    if not os.path.isdir( todir ):
                        message = 'Can not save copy of packages.'\
                                  ' No such directory'\
                                  ': %s' % todir
                        self.log.write_syslog_err( message )
                        self.log.write_stderr( message )
                    else:
                        for package in transaction.values():
                            try:
                                fromfile = package['localfilename']
                                basename = os.path.basename( fromfile )
                                tofile = os.path.join( todir, basename )
                                shutil.copyfile( fromfile, tofile )
                            except KeyError,e:
                                if not self.config['stage']:
                                    raise KeyError, e
                            except IOError:
                                message = 'Unable to move file %s to %s' % \
                                          (fromfile, tofile)
                                self.log.write_stderr( message )
                                self.log.write_syslog_err( message )
                if not string.lower( str(self.config["download_only"]) ) == \
                   "yes" and not \
                    string.lower( str(self.config["download_first"]) ) == \
                   "yes":
                    errmsg = self.install( transaction )
                    if errmsg:
                        errorflag = True
                    i = i +1
            if self.config['stage'] and errorflag:
                #
                # Not all packages where downloaded.
                #
                sys.exit(10)
            if not string.lower( str(self.config["download_only"]) ) == \
               "yes" and \
                string.lower( str(self.config["download_first"]) ) == \
               "yes":
                for transaction in transactions.values():
                    errmsg = self.install(transaction) 
                    if errmsg:
                        errorflag = True
                i = i +1
            if self.config["stage"]:
                pickle_file = \
                    os.path.join(self.config['cachedir'], self.config['resolved'])
                try:
                    os.remove(pickle_file)
                except OSError:
                    pass
            self.log.write_tty( "\n" )
            if errorflag:
                self.log.write_syslog_info( DEPENDENCY_ERROR_MESSAGE )
        return swupgrade


    def main(self):
        'Main function called by run(). Can be overloaded.'
        # Main function. Can be subclassed.
        self.swupgrade = None
        message = "Starting upgrade."
        self.log.write_syslog_info( message )
        self.log.write_stdout_verbose( message )
        selection = []
        packages = self.create_resolver_input(selection, 
                                                UPGRADE_FLAG)
        if not packages:
            message = "Your system is up to date." + 54*' '
            self.log.write_syslog_info( message )
            self.log.write_stdout_info( "\r%s" %message )
        else:
            self.swupgrade = self._main(packages)

        return self.swupgrade


    def run( self ):
        self.result = 0
        try:
            self.result = self.main()
        except ex.upgrade_error, errmsg:
            message = str(errmsg)
            self.log.write_syslog_err( message )
            self.log.write_stderr( message )
            raise
        # add handling log exc
        except ex.io_error, errmsg:
            errmsg = str( errmsg )
            self.log.write_stderr( errmsg )
            self.log.write_syslog_err( errmsg ) # syslog probably works.
            raise ex.upgrade_error, errmsg
        except:
            raise

        return self.result

                
class upgrade_package( Upgrade ):


    def __init__( self, install_list, configdict = None ):
        Upgrade.__init__( self, configdict )
        self.install_list = install_list

    
    
    def main( self ):
        message = "Starting upgrade of package."
        self.log.write_syslog_info( message )
        self.log.write_stdout_verbose(message)
        pickle_file = \
                os.path.join(self.config['cachedir'], self.config['resolved'])
        if self.config['stage'] and os.path.isfile(pickle_file):
            return self._main(None)
        packages = self.create_resolver_input(self.install_list,
                                              UPGRADE_FLAG)
        if packages:
            self._main(packages)



    
class install_package( Upgrade ):


    def __init__( self, install_list, configdict = None ):
        Upgrade.__init__( self, configdict )
        self.install_list = install_list


    def main( self ):
        message = "Starting install."
        self.log.write_syslog_info( message )
        self.log.write_stdout_verbose( message )
        pickle_file = \
                os.path.join(self.config['cachedir'], self.config['resolved'])
        if self.config['stage'] and os.path.isfile(pickle_file):
            return self._main(None)
        packages = self.create_resolver_input(self.install_list,
                                              INSTALL_FLAG)
        if packages:
            self._main(packages)





class list_latest( Upgrade ):


    def __init__( self, configdict = None ):
        Upgrade.__init__(self, configdict)


    def write( self ):
        self._generate_latest_lists()
        self.log.write_tty('\n')
        if not self.latest: return
        keys = self.latest.keys()
        keys.sort()
        for name in keys:
            version = self.latest[name]["version"]
            release = self.latest[name]["release"]
            uri = self.latest[name]["uri"]
            summary = self.latest[name]["summary"]
            message = "%s-%s-%s - %s" % ( name, version, release, summary )
            self.log.write_stdout( message )


    def main(self):
        self.write()



        
class list_new( Upgrade ):

    
    def __init__( self, configdict=None ):
        Upgrade.__init__(self, configdict)
        self._generate_latest_lists()
        if not self.latest: return
        

    def write( self ):
        self.log.write_tty('\n')
        keys = self.latest.keys()
        keys.sort()
        prospects = False
        for name in keys:
            if self.pkgdrv.is_installed( name ) == 2: continue
            prospects = True
            version = self.latest[name]["version"]
            release = self.latest[name]["release"]
            uri = self.latest[name]["uri"]
            summary = self.latest[name]["summary"]
            self.log.write_stdout ("%s %s-%s - %s" % ( name, version, release, summary ))
        if not prospects:
            message = "No new packages found."
            self.log.write_stdout( message )


    def main(self):
        self.write()


class list_alien( Upgrade ):

    def __init__(self, configdict=None ):
        Upgrade.__init__(self, configdict)

    def write ( self ):
        self._generate_latest_lists()
        if not self.latest: return
        keys = self.pkgdrv.get_installed()
        message = "\rThe following packages are alien according "\
                  + "to the configured repositories: "
        aliens = False
        for name in keys:
            if not self.latest.has_key(name): 
                pkginfo = self.pkgdrv.get_package(name)
                message += "\n%s-%s-%s"  % (name, pkginfo['version'], 
                                                    pkginfo['release'])
                aliens = True
        if not aliens:
            message = "\nNo alien packages found."

        self.log.write_stdout( message )

    def main(self):
        self.write()


class list_downgrade( Upgrade ):

    def __init__(self, configdict=None ):
        Upgrade.__init__(self, configdict)

    def write ( self ):
        self._generate_latest_lists()
        if not self.latest: return
        keys = self.pkgdrv.get_installed()
        downgrade = False
        message = "\rThe following installed packages have a higher " \
                    +"version number than the latest \n" \
                    +"available according to the configured repositories: "
        for package in self.latest.values():
            if self.pkgdrv.is_installed(package) == -1:
                installed = self.pkgdrv.get_package(package['name'])
                message +=  "\n%s (%s-%s vs. %s-%s)"\
                    %(installed["name"], installed['version'], 
                    installed['release'], package['version'], 
                    package['release'])
                downgrade = True
                    
        if not downgrade:
            message = "\nNo local package is newer than remote alternative."
            
        self.log.write_stdout( message )
            
    def main(self):
        self.write()


class list_upgrade( Upgrade ) :

    def __init__( self, configdict = None ):
        Upgrade.__init__(self, configdict)

    def write ( self ):
        packages = self.create_resolver_input([], UPGRADE_FLAG)
        if not packages:
            message = "\rYour system is up to date."
            self.log.write_syslog_info( message )
            self.log.write_stdout_info( "%s" %message )
        else:
            message = "\rThe following package(s) (including dependencies) will be upgraded: "
            self.log.write_stdout_info( "%s" %message )
            for package in packages:
                installed = self.pkgdrv.get_package(package['name'])
                if installed:
                    info = "%s (%s-%s vs. %s-%s)" \
                        %(package['name'], 
                            package['version'], package['release'],
                            installed['version'], installed['release'])
                else:
                    info = "%s (%s-%s)" %(package['name'], 
                        package['version'], package['release'])
                self.log.write_stdout_info( info )
            
    def main(self):
        self.write()

class search_package( Upgrade ):
    '''Search for packages by name, given a regexp search pattern,
    print result.'''
    
    
    def __init__( self, searchpattern, configdict = None ):
        Upgrade.__init__(self, configdict)
        self.pattern = self._compile_regexp(searchpattern)
        self.matches = []
    
    
    def search( self ):
        '''Search for packages whose name matches a regexp, and write the
        output to stdout.'''
        
        self._generate_latest_lists()
        if not self.latest:
            message = 'No package information found!'
            self.log.write_stderr( message )
            self.log.write_syslog_err( message )
            return
        
        keys = self.latest.keys()
        keys.sort()
        c = 0
        message = None
        for name in keys:
            if self.pattern.search(name):
                version = self.latest[name]["version"]
                release = self.latest[name]["release"]
                uri = self.latest[name]["uri"]
                summary = self.latest[name]["summary"]
                  
                verbose = 0
                if self.config['loglevel'] == log.LOGLEVEL_VERBOSE:
                    verbose = 1
                
                if message == None and verbose:
                    message = "%s (%s-%s) - %s\n" \
                        %(name, version, release, summary)
                elif message == None and not verbose:
                    message = "%s (%s-%s)\n" \
                        %(name, version, release)
                elif message and verbose:
                    message = message +  "%s (%s-%s) - %s\n" \
                        %(name, version, release, summary)
                elif message and not verbose:
                    message = message + "%s (%s-%s)\n" \
                        %(name, version, release)
                c = c + 1
        
        if message != None:
            sum = ( '\nFound ' + str(c) + ' package(s) matching "' +
                       self.pattern.pattern +  '":\n'  )
            self.log.write_tty(sum)
            self.log.write_stdout(string.strip(message))
        else:
            message = '\nFound 0 packages matching "' \
                            + self.pattern.pattern + '"\n'
            self.log.write_tty( message )
    
    
    def main( self ):
        self.search()




class search_file( Upgrade ):
    '''Search for packages providing file(s) matching the given searchpattern'''
    
    
    def __init__( self, searchpattern, configdict = None ):
        Upgrade.__init__(self, configdict)
        self.searchpattern = searchpattern
        self.pattern = self._compile_regexp(self.searchpattern)
        self.matches = []
        sitelist = self.config["sites"]
        sitelist.sort(self._sort_2d_sitelist)
        self.sites = {}
        for site in sitelist:
            (pri, latest_uri, regexp, name, enabled) = site
            if not enabled: continue
            if latest_uri[-10:] == "latest.rdf":
                list_uri = re.sub('latest.rdf', 'filelist', latest_uri)
            else:
                list_uri = os.path.join(latest_uri, 'filelist')
            pri = abs(int(pri))
            self.sites[list_uri] = name
            
    
    
    def retrieve_filelist( self, uri ):
        '''Get filelist from uri, and save. Returns a table containing
        the lines in the list.'''
        
        if uri[-3:] == '.gz':
            md5sum_uri = uri[:-3] + '.md5'
            noncompressed_uri = 'rdfs/'+ uri[:-3]
        else:
            noncompressed_uri = 'rdfs/'+ uri
            md5sum_uri = uri + '.md5'
        filetab = None
        
        if self.md5sum_isequal(md5sum_uri, noncompressed_uri):
            local_filelist = os.path.join(self.config['listsdir'], uri)
            local_filelist = utils.normalize_uri(local_filelist)
            if os.path.isfile(local_filelist):
                fd = open(local_filelist)
                filetab = fd.readlines()
                fd.close()

        if not filetab:
            #Try DL'ing gzipped file first.
            if uri[-3:] != '.gz':
                try:
                    local_filelist = self.download_file(uri + '.gz', TYPE=2)
                except IOError, ex.download_error:#necessary?
                    local_filelist = self.download_file(uri, TYPE=2)
                except:
                    raise

            fd = open(local_filelist)
            filetab = fd.readlines()
            fd.close()
            # move filelist to listdir
            savefile = os.path.join(self.config['listsdir'], uri)
            savefile = utils.normalize_uri(savefile)
            os.renames(local_filelist, savefile)
            self.md5sum_set(md5sum_uri,noncompressed_uri)
        return filetab
    
    
    def get_filelists(self):
        '''Returns a dictionary containing a table of files, with
        uri as key.'''
        
        found_valid_site = 0
        filelists = {}
        for list_uri in self.sites.keys():
            try:
                sitename = self.sites[list_uri]
                if sitename == "None":
                    message = "Fetching file info '%s'" %list_uri
                else:
                    message = "Fetching file info for site: %s" %sitename
                self.log.write_syslog_info( message )
                filelists[list_uri] = self.retrieve_filelist(list_uri)
                found_valid_site = 1
            except ex.download_error, errmsg:
                errmsg = "%s Skipping." % errmsg
                self.log.write_syslog_err( message )
                self.log.write_stderr(errmsg)
                continue
            except:
                raise

        if not found_valid_site == 1:
            self.log.write_syslog_err(NoValidSiteFoundError)
            self.log.write_stderr("\n%s" %NoValidSiteFoundError)
            sys.exit(1)
        return filelists

    
    def search( self, listdict):
        '''Search for packages providing files that matches the
        searchpattern. Prints output to stdout'''
        
        matched_at_all = False
        for uri in listdict.keys():
            message = "\n"
            found = False
            for line in listdict[uri]:
                if line[0] == "[":
                    package = line[10:-15]
                    nameparts = string.split(package, '-')
                    nameparts.reverse()
                    release = nameparts[0]
                    nameparts.remove(nameparts[0])
                    version = nameparts[0]
                    nameparts.remove(nameparts[0])
                    nameparts.reverse()
                    name = nameparts[0]
                    nameparts.remove(nameparts[0])
                    for part in nameparts:
                        name = "%s-%s" %(name, part)
                    package = "%s (%s-%s)" %(name, version, release)
                    continue
                matched = self.pattern.search(line)
                if matched:
                    found = True
                    sitename = self.sites[uri]
                    if sitename == "None":
                        message += "[Unnamed] %s: %s" \
                            %(package,line)
                    else:
                        message += "[%s] %s: %s" %(sitename,package,line)
            if found:
                matched_at_all = True
                self.log.write_stdout(message)
        if not matched_at_all:
            message = "Found 0 files matching \"%s\"\n" %self.searchpattern
            self.log.write_tty(message)
    
    
    def main( self ):


        filelists = self.get_filelists()
        if not filelists:
            self.log.write_stderr('No file information found!')
            return
        
        self.search(filelists)

class describe( Upgrade ):
    '''show description for the package given as argument'''
    
    def __init__( self, configdict = None ):
        Upgrade.__init__(self, configdict)
        self.target = configdict["descriptor"]
        self.summary = None
    
    
    def find_package( self ):
        '''Find package that fits descriptor'''
        
        self._generate_latest_lists()
        
        if not self.latest:
            message = 'No package information found!'
            self.log.write_stderr( "" )
            self.log.write_stderr( message )
            self.log.write_syslog_err( message )
            return
        
        pkg = {}
        if self.latest.has_key(self.target):
            pkg = self.latest[self.target]
        else:
            message = "No package named '%s' found!" %self.target
            self.log.write_stderr( "" )
            self.log.write_stderr( message)
            self.log.write_syslog_err( message )
            return

        uri = pkg['uri']
        try:
            (baseuri, basename) = os.path.split(uri)
            self.log.write_tty('Parsing file: %s -' % basename)
            local_filename = self.download_file( uri,TYPE=2 )
            package = self.reader.read_package( local_filename, baseuri )
            self.log.write_tty('\rParsing file: %s - done' % basename)
        except ex.spi_parse_error:
            raise ex.parse_error, "Unable to parse file '%s'" % uri
        except:
            raise


        result = "\n"

        
        if package.has_key("name"):
            result += "Name: %s\n" %package["name"]
        if package.has_key("epoch"):
            result += "Epoch: %s\n" %package["epoch"]
        if package.has_key("version"):
            result += "Version: %s\n" %package["version"]
        if package.has_key("release"):
            result += "Release: %s\n" %package["release"]
        if package.has_key("distribution"):
            result += "Distribution: %s\n" %package["distribution"]
        if package.has_key("vendor"):
            result += "Vendor: %s\n" %package["vendor"]
        if package.has_key("copyright"):
            result += "License: %s\n" %package["copyright"]
        if package.has_key("group"):
            result += "Group: %s\n" %package["group"]
        if package.has_key("build_date"):
            result += "Build date: %s\n" %package["build_date"]
        if package.has_key("arch"):
            result += "Arch: %s\n" %package["arch"]
        if package.has_key("os"):
            result += "OS: %s\n" %package["os"]
        if package.has_key("size"):
            result += "Size: %s\n" %package["size"]
        if package.has_key("md5sum"):
            result += "Md5sum: %s\n" %package["md5sum"]
        if package.has_key("uri"):
            result += "Uri: %s\n" %package["uri"]
        if package.has_key("signature"):
            result += "Sign: %s\n" %package["signature"]
        if package.has_key("requirements"):
            requires = package["requirements"]
            result += self._dicttostring(requires, "Requires")
        if package.has_key("conflicts"):
            conflicts = package["conflicts"]
            result += self._dicttostring(conflicts, "Conflicts")
        if package.has_key("summary"):
            result += "\nSummary: %s\n" %package["summary"]
        if package.has_key("description"):
            result += "\nDescription: %s\n" %package["description"]

        self.log.write_stdout( result )
    
        return

    def _dicttostring(self,dict,outstring):
        ''' Formats a given dict with package info into a nicely formatted
        string. '''
        reqmess = ""
        handled = {}
        for req in dict:
            name = req['name']
            version = req['version']
            release = req['release']
            if handled.has_key(name):
                continue
            reqmess += '\n'
            if req.has_key('flag'):
                req['operator'] = req['flag']
            if req['operator'] == '':
                reqmess += "\t%s" %name
            else:
                reqmess += "\t%s (%s %s" %(name, req['operator'], version)
                if not release == '':
                    reqmess += "-%s" %release
                reqmess += ")"
            handled[name] = 1
        if not reqmess == "":
            return "%s: %s\n" %(outstring,reqmess)
        else:
            return ''
    
    def main( self ):
        self.find_package()

class what_provides( Upgrade ):
    '''Retrieves the remote resource information and prints packages that 
    provide the given resource.'''
    
    def __init__(self, configdict = None):
        Upgrade.__init__(self, configdict)
        self.target = configdict["descriptor"]
    
    
    def find_resource(self):
        '''Find resource that fits descriptor'''
        
        self._generate_resources()
        
        if not self.resources:
            message = 'No resource information found!'
            self.log.write_stderr('')
            self.log.write_stderr(message)
            self.log.write_syslog_err(message)
            return
        
        pkg = {}
        providers = self._get_resource_providers(self.target)
        if len(providers) == 0:
            message = "No resource named '%s' found!" %self.target
            self.log.write_stderr('')
            self.log.write_stderr(message)
            self.log.write_syslog_err(message)
            return

        already_found = []
        result = ''
        for provider in providers:
            if not provider['name'] in already_found:
                result += '%s-%s-%s\n' %(provider['name'], \
                                            provider['version'], \
                                            provider['release'])
                already_found.append(provider['name'])
        ttyresult = "\n\nFound %d package(s) providing the resource '%s'\n" \
                %(len(already_found),self.target)

        self.log.write_tty(ttyresult)
        self.log.write_stdout(result)

    
    def main( self ):
        self.find_resource()

class search_resource( Upgrade ):
    '''Search for resources by name, given a regexp search pattern,
    print result.'''
    
    
    def __init__( self, searchpattern, configdict = None ):
        Upgrade.__init__(self, configdict)
        self.pattern = self._compile_regexp(searchpattern)
        self.matches = []
    
    
    def search( self ):
        '''Search for resources whose name matches a regexp, and write the
        output to stdout.'''
        
        self._generate_resources()
        if not self.resources:
            message = 'No resource information found!'
            self.log.write_stderr( message )
            self.log.write_syslog_err( message )
            return
        
        keys = self.resources.keys()
        keys.sort()
        c = 0
        message = ""
        for name in keys:
            if self.pattern.search(name):
                message += "%s\n" %name
                c += 1
        
        if len(message) > 0:
            sum = ( '\nFound ' + str(c) + ' resource(s) matching "' +
                       self.pattern.pattern +  '":\n'  )
            self.log.write_tty(sum)
            self.log.write_stdout(string.strip(message))
        else:
            message = '\nFound 0 resources matching "' \
                            + self.pattern.pattern + '"\n'
            self.log.write_tty( message )
    
    
    def main( self ):
        self.search()
