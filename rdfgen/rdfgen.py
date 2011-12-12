#!/usr/bin/env python
# -*- python -*-
#  Copyright 2003 - 2004 Tor Hveem - <tor@bash.no>
# $Id: rdfgen.py,v 1.50 2005/06/13 09:04:18 christht Exp $

DEBUG = True
error = 'rdfgen.error'

import os, sys, string, urlparse, getopt, re, types
from swuplib.driver import pkgdriver
from swuplib import config
from swuplib import utils
from swuplib import download
from swuplib import spiparser
from swuplib import gpg
from swuplib import log
from swuplib import help
from swuplib import ex
import rdf 



SHORT_SWITCHES = "bhqvScCo:P:g:k:L:s:"
LONG_SWITCHES = ["help", 
                 "version", 
                 "quiet", 
                 "sign",
                 "nocompress",
                 "keyid", 
                 "password", 
                 "gpghomedir"]

# Defaults
RDFDIR = "rdfs"
RESOURCEDIRNAME = "resources"
RESOURCESFILENAME = "resources.rdf"
PACKAGEDIRNAME = "packages"
PACKAGEPREFIX = ""
SIGPREFIX = ""
LATESTFILENAME = "latest.rdf"
RESOURCELIST_FILENAME = "resourcelist.rdf"
FILELISTNAME = "filelist"
LINK_RESOURCELISTS = []
LINK_FILELISTS = []
LINK_LIST = []
PGPHOMEDIR = os.path.join(os.path.expanduser("~"),'.gnupg')
PGPFILE = os.path.join(os.path.expanduser("~"),'.pass')
PGPID = ""
SIGN = False
COMPRESS = True
OLDSTYLERESOURCES = False

# exceptions

def escape_capabilityname(capabilityname):
    # Hack to escape / in requirements.
    # Example: /sbin/restart_maybe -> _sbin_restart__maybe
    capabilityname = string.replace(capabilityname, "_", "__")
    capabilityname = string.replace(capabilityname, "/", "_")
    return capabilityname


class rdfgen:
    bracket_regexp = re.compile('^\[.*\]$')

    def __init__(self, rdfdir, link_list=[], quiet=0):
        self.rdfdir = rdfdir
        self.resourcedirname = RESOURCEDIRNAME
        self.packagedirname = PACKAGEDIRNAME
        self.packageprefix = PACKAGEPREFIX
        self.sigprefix = SIGPREFIX
        self.latestfilename = LATESTFILENAME
        self.resourcelist_filename = RESOURCELIST_FILENAME
        self.resources_filename = RESOURCESFILENAME
        self.filelistname = FILELISTNAME
        self.link_resourcelists = LINK_RESOURCELISTS
        self.link_filelists = LINK_FILELISTS
        self.link_list = link_list
        self.filelists = {}
        self.files = {}
        self.capabilities = {}
        self.resources = {}
        self.packages = {}
        self.latest = {}
        self.requirements = {}
        self.writer = rdf.writer()
        self.reader = spiparser.rdf_reader()
        self.quiet = quiet
        self._init_config()
        self._init_log()
        self._init_downloader()
        self._flush_cache()
        self.driver = pkgdriver.pkgdriver(self.config)


    def _init_config(self):
        "Initialize config,"
        self.config = config.parse()
        if self.quiet:
            self.config['loglevel'] = log.LOGLEVEL_QUIET
        else:
            self.config['loglevel'] = log.LOGLEVEL_NORMAL
        self.config['cachedir'] = \
            os.path.join(os.path.expanduser("~"),'.rdfgen/cache')
        self.config['tmpdir'] = \
            os.path.join(os.path.expanduser("~"),'.rdfgen/spool')

    def _init_log(self):
        "Initialize log."
        self.log = log.log(self.config['loglevel'], True )
            
    def _init_downloader(self):
        "Initialize downloader."
        try:
            self._downloader = download.download(self.config, PGPHOMEDIR)
        except ex.download_error, errmsg:
            raise ex.upgrade_error, errmsg
        except:
            raise

    def _flush_cache(self):
        "Flush cache."
        flusher = download.Flush(self.config)
        flusher.run()

    def download_file(self, uri, siguri=None, CHECKSIG=1, TYPE=1):
        "Download file from uri and check signature. Returns local filename."
        "TYPE is: 1 = rpm-related, 2 = rdf-related"
        try:
            filename = self._downloader.download(uri, siguri, CHECKSIG, TYPE)
            return filename
        except ex.auth_error, errmsg:
            raise ex.auth_error, errmsg
        except ex.download_error, errmsg:
            raise ex.download_error, errmsg
        except:
            raise

    def get_remote_info(self):
        force_old_style = False
        files = {}
        resources = {}
        if not self.link_list:
            return (files, resources)
        
        self.link_filelists = []
        self.link_resourcelists = []
        for baseuri in self.link_list:
            fileuri = utils.normalize_uri(baseuri + FILELISTNAME)
            self.link_filelists.append(fileuri)
            resuri = utils.normalize_uri(baseuri + RESOURCESFILENAME)
            try:
                newresources = self.get_resources(resuri)
                newresources.update(resources)
                resources = newresources
            except Exception, e:
                force_old_style = True
                reslisturi = \
                    utils.normalize_uri(baseuri + RESOURCELIST_FILENAME)
                self.link_resourcelists.append(reslisturi)
                pass
        if force_old_style and not OLDSTYLERESOURCES:
            #
            # Ok. We'll need to fore Old-style generation
            #
            globals()['OLDSTYLERESOURCES'] = True
            message = "At least one of the remote sites offers only old style "\
                + "repository.\n"\
                + "This forces us to use backward compatibility mode.\n"
            sys.stderr.write(message)
        files = self.get_filelists()
        newresources = self.get_resourcelists()
        newresources.update(resources)
        resources = newresources
        return (files, resources)

    def get_resources(self, uri):
        resources = {}
        protocol, server, path = urlparse.urlparse(uri)[:3]
        baseuri = os.path.dirname(uri)
        if not server:
            baseuri = os.path.join('../..', baseuri)
        if not self.quiet: 
            self.log.write_stdout('Retrieving resources: %s' % uri)
        try:
            gzuri = utils.normalize_uri(uri + '.gz')
            retr_file = self.download_file(gzuri,TYPE=2)
        except:
            try:
                retr_file = self.download_file(uri,TYPE=2)
            except:
                if not quiet:
                    message = "No %s found, %s scheduled for download." \
                        %(RESOURCESFILENAME, RESOURCELIST_FILENAME)
                    self.log.write_stdout(message)
                raise
            pass
        resources = self.reader.read_resources(retr_file, baseuri)
        return resources

    def get_filelists(self):
        files = {}
        for uri in self.link_filelists:
            protocol, server, path = urlparse.urlparse(uri)[:3]
            rdfdir = os.path.dirname(path)
            if not self.quiet: 
                self.log.write_stdout('Retrieving file list: %s' % uri)
            try:
                gzuri = utils.normalize_uri(uri + '.gz')
                file = self.download_file(gzuri,TYPE=2)
            except:
                file = self.download_file(uri,TYPE=2)
                pass
            fd = open(file)
            lines = fd.readlines()
            fd.close()
            baseuri = os.path.dirname(uri)
            if not self.bracket_regexp.match(lines[0]):
                raise ex.format_error, 'Wrong format in filelist: %s' % uri
            for line in lines:
                if self.bracket_regexp.match(line):
                    pkg = string.replace(line, '[', ']')
                    pkg = string.replace(pkg, ']', '')
                    pkg = os.path.join(rdfdir, pkg)
                    pkg = urlparse.urlunparse((protocol, server, pkg,
                                               '', '', ''))
                    files[pkg] = []
                else:
                    files[pkg].append(string.strip(line))
        return files


    def get_resourcelists(self):
        resources = {}
        for uri in self.link_resourcelists:
            protocol, server, path = urlparse.urlparse(uri)[:3]
            baseuri = os.path.dirname(uri)
            if not server:
                baseuri = os.path.join('../..', baseuri)
            if not self.quiet: 
                self.log.write_stdout('Retrieving resource list: %s' % uri)
            retr_file = self.download_file(uri,TYPE=2)            
            newresources = self.reader.read_resourcelist(retr_file, baseuri)
            newresources.update(resources)
            resources = newresources
        return resources

        
    def prepare_package(self, filename):
        if not self.quiet: 
            self.log.write_stdout('Parsing RPM headers: %s' % filename)
        pkgdata = self.driver.get_package(filename, True)
        name = pkgdata['name']
        basename = pkgdata['basename']
        self.filelists[basename] = pkgdata['filelist']            
        
        if self.packages.has_key(basename):
            raise ex.duplicate_error, 'Duplicate packages found: %s' % basename
        # Adding the packageinfo to a dictionary with basename as key.
        self.packages[basename] = pkgdata

        # Adding a list of latest version packages with name as key.
        if self.latest.has_key(name):
            old = self.latest[name]
            if self.driver.version_compare(old, pkgdata) < 0:
                self.latest[name] = pkgdata
        else:
            self.latest[name] = pkgdata
            
        # Adding the packageinfo to the capability dictionary with
        # package name as key.
        if not self.capabilities.has_key(name):
            self.capabilities[name] = []
        self.capabilities[name].append(pkgdata)

        # Adding the packageinfo to the capability dictionary with the
        # "provide"-string as key.
        provides = pkgdata['provides']
        if provides:
            for capability in  provides:
                if not self.capabilities.has_key(capability):
                    self.capabilities[capability] = []
                self.capabilities[capability].append(pkgdata)

        # Adding the packageinfo to a dictionary of requirements with
        # capability (requirement) as key.
        requires = pkgdata['requires']
        if requires:
            for capability in requires:
                if not self.requirements.has_key(capability):
                    self.requirements[capability] = []
                self.requirements[capability].append(pkgdata)

    def generate_packages(self):
        package_formatter = rdf.package_formatter(\
            self.writer, self.resources, self.resourcedirname,
            self.packagedirname, self.packageprefix, self.sigprefix)

        # Write rdf-file for package here.
        for basename in self.packages.keys():
            if not self.quiet: 
                self.log.write_stdout('Writing rdf for package: %s' % basename)
            pkgdata = self.packages[basename]
            outfilename = os.path.join(self.rdfdir, self.packagedirname,
                                       (basename + ".rdf"))
            outfile = open(outfilename, "w")        
            package_formatter.set_fd(outfile)
            package_formatter.reset()
            package_formatter.feed(pkgdata)
            outfile.close()
            #Sign file
            if SIGN and not PGPID == "":
                gpg.gpg_signfile(PGPFILE, PGPID, PGPHOMEDIR, outfilename)



    def generate_resources(self):
        if not self.quiet: 
            self.log.write_stdout('Writing resources.rdf')
        resources_formatter = rdf.resources_formatter(self.writer, 
                                                    self.packagedirname)
        # resources.rdf
        outfilename = os.path.join(self.rdfdir, self.resources_filename)
        outfile = open(outfilename, "w")
        resources_formatter.set_fd(outfile)
        resources_formatter.reset()
        resources_formatter.feed(self.capabilities)
        outfile.close()
        #Md5
        utils.md5sumtofile(outfilename)
        if COMPRESS:
            utils.compress_file(outfilename)
        #Sign file
        if SIGN and not PGPID == "":
            gpg.gpg_signfile(PGPFILE, PGPID, PGPHOMEDIR, outfilename)
        if OLDSTYLERESOURCES:
            #
            # Old style resources:
            #
            resource_formatter = rdf.resource_formatter(self.writer,
                                                        self.packagedirname)
            resourcelist_formatter = rdf.resourcelist_formatter(\
                self.writer, self.resourcedirname)
            capfilenames = {}
            for capabilityname in self.capabilities.keys():
                if not self.quiet: 
                    self.log.write_stdout(\
                            'Writing rdf for resource: %s\n' % capabilityname)
                capabilitydata = self.capabilities[capabilityname]
                escaped_capabilityname = rdf.escape_capabilityname(\
                    capabilityname)
                capfilename = os.path.join(self.resourcedirname,
                                           (escaped_capabilityname + ".rdf"))
                outfilename = os.path.join(self.rdfdir, capfilename)
                capfilenames[capabilityname] = capfilename
                outfile = open(outfilename, "w")
                resource_formatter.set_fd(outfile)
                resource_formatter.reset()
                resource_formatter.feed(capabilityname, capabilitydata)
                outfile.close()
                #Sign file
                if SIGN and not PGPID == "":
                    gpg.gpg_signfile(PGPFILE, PGPID, PGPHOMEDIR, outfilename)

            
            outfilename = os.path.join(self.rdfdir, self.resourcelist_filename)
            outfile = open(outfilename, "w")
            resourcelist_formatter.set_fd(outfile)
            resourcelist_formatter.reset()
            resourcelist_formatter.feed(capfilenames)
            outfile.close()
            #Md5
            utils.md5sumtofile(outfilename)
            if COMPRESS:
                utils.compress_file(outfilename)
            #Sign file
            if SIGN and not PGPID == "":
                gpg.gpg_signfile(PGPFILE, PGPID, PGPHOMEDIR, outfilename)
        else:
            self.log.write_stdout("Skipping old style resources.\n")
        

    def generate_latestlist(self):
        packagelist_formatter = rdf.packagelist_formatter(\
            self.writer, self.packagedirname, self.resourcelist_filename,
            self.resources_filename)

        outfilename = os.path.join(self.rdfdir, self.latestfilename)
        outfile = open(outfilename, "w")

        packagelist_formatter.set_fd(outfile)
        packagelist_formatter.reset()
        packagelist_formatter.feed(self.latest)
        outfile.close()
        #Md5
        utils.md5sumtofile(outfilename)
        #Compress
        if COMPRESS:
            utils.compress_file(outfilename)
        #Sign file
        if SIGN and not PGPID == "":
            gpg.gpg_signfile(PGPFILE, PGPID, PGPHOMEDIR, outfilename)

    def generate_filelist(self):
        filelist_formatter = rdf.filelist_formatter(self.packagedirname)
        outfilename = os.path.join(self.rdfdir, self.filelistname)
        outfile = open(outfilename, "w")
        filelist_formatter.set_fd(outfile)
        filelist_formatter.reset()
        filelist_formatter.feed(self.filelists)
        outfile.close()
        #Md5
        utils.md5sumtofile(outfilename)
        if COMPRESS:
            utils.compress_file(outfilename)
        #Sign file
        if SIGN and not PGPID == "":
            gpg.gpg_signfile(PGPFILE, PGPID, PGPHOMEDIR, outfilename)

    def get_resourcefilename(self, capname):
        return os.path.join(self.resourcedirname,
                            escape_capabilityname(capname)+'.rdf')

    def generate_rdfs(self, filenames):

        for filename in filenames:
            self.prepare_package(filename)
            #Sign file
            if SIGN and not PGPID == "":
                signfile = ''
                if not self.sigprefix == '':
                    op = os.path
                    packagerdfpath = op.join(self.rdfdir, 'packages')
                    sigpath = op.join(packagerdfpath, self.sigprefix)
                    signfile = op.join(sigpath,filename+'.asc')
                    sigextradir = op.join(sigpath,op.dirname(filename))
                    if not op.isdir(sigextradir):
                        os.makedirs(sigextradir)
                gpg.gpg_signfile(PGPFILE, PGPID, PGPHOMEDIR, filename,signfile)

        # Checking if there are any requirements on capabilities that are not
        # found in the capabilities dictionary. If so, look for the
        # capability in the file lists, and add the capability to the
        # capability dictionary with the packageinfo for the package in
        # which the file was found.
        (incl_files, incl_resources) = self.get_remote_info()

        # Update resources from capabilities.
        for capname in self.capabilities.keys():
            self.resources[capname] = os.path.join(\
                '..', self.get_resourcefilename(capname))

        errors = ''
        for requirement in self.requirements.keys():
            reqfound = False
            if not self.resources.has_key(requirement):
                #
                # Check if requirement is a file in a local package
                #
                for basename in self.packages.keys():
                    filelist = self.filelists[basename]
                    if requirement in filelist:
                        reqfound = True
                        packageinfo = self.packages[basename]
                        if not self.capabilities.has_key(requirement):
                            self.capabilities[requirement] = []
                        self.capabilities[requirement].append(packageinfo)
                        self.resources[requirement] = \
                            os.path.join(\
                            '..', self.get_resourcefilename(requirement))

            # Now search linked resources
            if not reqfound and requirement in incl_resources.keys():
                reqfound = True
                if not OLDSTYLERESOURCES:
                    #
                    # We are happy as long as the requirement is provided
                    # remotely. Continue.
                    #
                    self.resources[requirement] = False
                    continue
                resourceinfo = []
                item = incl_resources[requirement]
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
                    filename = self.download_file(uri)
                        
                    resourceinfo = self.reader.read_resource(\
                        filename, baseuri)
                else:
                    #
                    # New style: info was part of resource.rdf
                    #
                    resourceinfo = item
                    
                for index in range(len(resourceinfo)):
                    #
                    # Go through each resource-provider
                    #
                    resource = resourceinfo[index]
                    
                    uri = resource['uri']
                    baseuri = os.path.dirname(uri)
                    filename = self.download_file(uri)
                    packageinfo = self.reader.read_package_short(\
                        filename, baseuri)
                    packageinfo['uri'] = uri
                    if not self.capabilities.has_key(requirement):
                        self.capabilities[requirement] = []
                    self.capabilities[requirement].append(packageinfo) 
                    self.resources[requirement] = os.path.join(\
                        '..', self.get_resourcefilename(requirement))
            if not reqfound:
                # Now search included filelists.
                for uri in incl_files.keys():
                    if requirement in incl_files[uri]:
                        reqfound = True
                        if not OLDSTYLERESOURCES:
                            #
                            # We are happy as long as the requirement is
                            # provided remotely. Continue.
                            #
                            self.resources[requirement] = False
                            continue
                        # We found the file. It is in package with package
                        # description found at <uri>. Generate a resource
                        # for this file locally.

                        protocol, server, path = urlparse.urlparse(uri)[:3]
                        if not (protocol and server):
                            path = os.path.join('../..', path)
                            baseuri = os.path.dirname(path)
                        else:
                            baseuri = os.path.dirname(uri)
                        filename = self.download_file(uri)
                        
                        packageinfo = self.reader.read_package_short(\
                            filename, baseuri)
                        packageinfo['uri'] = uri
                        if not self.capabilities.has_key(requirement):
                            self.capabilities[requirement] = []
                        self.capabilities[requirement].append(packageinfo) 
                        self.resources[requirement] = os.path.join(\
                            '..', self.get_resourcefilename(requirement))
                       
            if reqfound:
                continue
            if not self.capabilities.has_key(requirement):
                requiringPackages = []
                for package in self.requirements[requirement]:
                    requiringPackages.append(package['name'])
                errors += "%s is missing the resource %s\n" \
                        % (requiringPackages,requirement)

        if errors:
            sys.stderr.write("%s\n" %errors)
                
        # Write a one-file package listing with name, version, release and
        # resource-pointer to rdf for package.
        # Send whole dict of packages
        self.generate_latestlist()

        # Write rdf-file for resources/capabilities here.
        self.generate_resources()

        # Write package rdfs.
        self.generate_packages()

        # Write filelist.
        self.generate_filelist()


    def rdfify_files(self, of_files):
        to_directory = os.getcwd()
        resourcedir = os.path.join(self.rdfdir,self.resourcedirname)
        packagedir = os.path.join(self.rdfdir,self.packagedirname)
        #sigdir is relative to packagedir
        sigdir = os.path.join(packagedir,self.sigprefix)
        if not os.path.isdir(resourcedir):
            os.makedirs(resourcedir)
        if not os.path.isdir(packagedir):
            os.makedirs(packagedir)
        if not os.path.isdir(sigdir):
            os.makedirs(sigdir)
        for i in range( len(of_files)):
            of_files[i] = string.strip( of_files[i] )
        self.generate_rdfs( of_files )
        if not OLDSTYLERESOURCES and os.path.isdir(resourcedir):
            os.removedirs(resourcedir)


    def main(self, of):
        realfilelist = []
        for fileordir in of:
            if os.path.isdir(fileordir):
               filelist = os.listdir(fileordir)
               for file in filelist:
                   realfile = os.path.join(fileordir,file)
                   if os.path.isfile(realfile) and \
                       os.path.splitext(realfile)[1].lower() == ".rpm":
                       realfilelist.append(realfile)
            elif os.path.isfile(fileordir) and \
                       os.path.splitext(fileordir)[1].lower() == ".rpm":
                       realfilelist.append(fileordir)
        self.rdfify_files(realfilelist)





def generate(files, rdfdir=RDFDIR, link_list=[], quiet=0):
    
    generator = rdfgen(rdfdir, link_list, quiet)
    generator.main(files)



def main(args):
    try:
        opts, args = getopt.getopt(args, SHORT_SWITCHES, LONG_SWITCHES)
        optsdict = {}
        for (opt,val) in opts:
            optsdict[opt] = val
        switches = optsdict.keys()
    except getopt.GetoptError, msg:
        sys.stderr.write(str(msg) + "\nUse -h for help.\n")
        sys.exit(1)
    except:
        raise

    resources_filename = RESOURCESFILENAME
    if (not switches) and (not args):
        help.helpme(False)
        sys.exit(1)
    
    if ('-h' in switches) or ('--help' in switches):
        help.helpme(False)
        sys.exit(0)

    if ('-v' in switches) or ('--version' in switches):
        help.version(False)
        sys.exit(0)

    if '-o' in switches:
        rdfdir = optsdict['-o']
    else:
        rdfdir = RDFDIR

    if '-L' in switches:
        link_list = []
        for (opt, optval) in opts:
            if opt == "-L":
                link_list.append(optval)
    else:
        link_list = []

    if '-S' in switches or '--sign' in switches:
        globals()['SIGN']=True

    if '-C' in switches or '--nocompress' in switches:
        globals()['COMPRESS']=False

    if '-k' in switches:
        globals()['PGPID'] = optsdict['-k']
        
    if '-P' in switches:
        globals()['PGPFILE'] = optsdict['-P']

    if '-g' in switches:
        globals()['PGPHOMEDIR'] = optsdict['-g']

    if '-b' in switches:
        globals()['OLDSTYLERESOURCES'] = True

    if '-q' in switches or '--quiet' in switches:
        quiet = 1
    else:
        quiet = 0

    if '-s' in switches:
        globals()['SIGPREFIX'] = optsdict['-s']

    
    try:
        generate(args, rdfdir, link_list, quiet)
    except:
        raise
    
    
if __name__ == '__main__':
    main(sys.argv)



