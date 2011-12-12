#!/usr/bin/python
# $Id: download.py,v 1.52 2005/07/20 14:41:58 christht Exp $

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

import sys, time, os, urlparse, string, re, shutil
from swuplib import gpg
from swuplib import log
from swuplib import ex
from swuplib import utils
import urllib

DEBUG = 0

# some constants/defaults
CACHEDIR = '/var/cache/swup'
TMPDIR = '/var/spool/swup/tmp'
GNUPGDIR='/etc/swup/gnupg'
SIGNATURE_APPEND = '.asc'

# DNS cache trick
import socket
socket._getaddrinfo = socket.getaddrinfo
_dns_cache = {}
def _caching_getaddrinfo(*args, **kwargs):
    try:
        query = (args)
        res = _dns_cache[query]
        return res
    except KeyError:
        res = socket._getaddrinfo(*args, **kwargs)
        _dns_cache[args] = res
        return res
socket.getaddrinfo = _caching_getaddrinfo

class Flush:
    def __init__(self, configdict=None):
        "Set up configuration and run initialization functions."
        self.config = configdict
        self.cachedir = configdict['cachedir']
        self.log = log.log(self.config["loglevel"], False)
    
    def run ( self, site=None,flush_lists=True,flush_rpms=True ):
        flushdirs = ['rpms','rdfs','lists']
        if not flush_lists:
            flushdirs.remove('lists')
        if not flush_rpms:
            flushdirs.remove('rpms')
        urllib.urlcleanup()

        if os.path.isdir(self.cachedir):
            for subdir in flushdirs: 
                dir = os.path.join(self.cachedir, subdir)
                if site:
                    dir = os.path.join(dir, site)
                if os.path.isdir(dir):
                    shutil.rmtree(dir)
                if not site:
                    os.mkdir(dir, 0755)
            if not site:
                #
                # Now let'a recreate the infrastructure:
                #
                for subdir in ['file:', 'http:', 'https:', 'ftp:']:
                    for type in ['rpms/','rdfs/']:
                        sd = type + subdir
                        dir = os.path.join(self.cachedir, sd)
                        os.mkdir(dir, 0755)
        
    def flush_transaction(self, transaction):
        '''Deletes local files in cache given an swup transaction'''
        for package in transaction.values():
            self.log.write_stdout_verbose('Erased %s.' \
                    %os.path.basename(package['localfilename']))
            os.unlink(package['localfilename'])
            


class download:

    def __init__( self, config, gnupgdir=GNUPGDIR, log=None, cachedir=CACHEDIR, tmpdir=TMPDIR):
        self.log = log
        self.cachedir = cachedir
        self.tmpdir = tmpdir
        self.gnupgdir = gnupgdir
        self.auth_handler = None
        self.config = config
        try:
            import urllib2
            self.opener = urllib2
            self.auth_handler = urllib2.HTTPBasicAuthHandler( \
                urllib2.HTTPPasswordMgrWithDefaultRealm())
            handler = self.opener.build_opener(self.auth_handler,\
                            urllib2.CacheFTPHandler())
            self.opener.install_opener(handler)
        except ImportError:
            self.opener = urllib
        except:
            raise
        
        if not os.path.isdir( tmpdir ):
            try:
                if os.path.exists( tmpdir ):
                    os.remove( tmpdir )
                os.makedirs( tmpdir )
            except (OSError, IOError), err:
                raise ex.download_error, err
            except:
                raise


    def _download_callback(self, blocknum, blocksize, filesize, filename, 
        TYPE=1):
        #if size == -1: don't use size in calculation.

        #We don't provide status for .asc,.md5 files
        if filename[-3:] in ['asc','md5']: return 

        if blocknum == 0:
            self._bytes_read = 0
            self._time_used = 0
            self._time = time.time()

        self._bytes_read = self._bytes_read + blocksize

        if filesize not in [-1,0]:
            if self._bytes_read > filesize:
                percent = 100
                self._bytes_read = filesize
            else:
                tmptime = time.time()
                self._time_used = self._time_used + (tmptime - self._time)
                self._time = tmptime
                percent = self._bytes_read / float(filesize) * 100
            if not self._time_used <= 0:
                (speed, speed_prefix) = utils._byte_convert( self._bytes_read/
                                                      float(self._time_used))
            else:
                speed, speed_prefix = 0, 'k'
            
            (size, size_prefix) = utils._byte_convert( filesize )
            (read, read_prefix) = utils._byte_convert( self._bytes_read )
            message = "\rDownloading "\
                      "%-24s (%-7s%-1sB of %-7s%-1sB, %-3d%%, %-7s%-1sB/s)"%\
                      (self._now_downloading[:21]+"...", read, read_prefix,
                       size, size_prefix, percent, speed, speed_prefix)
            progress = "Downloading %s %s %s %s" \
                %(self._now_downloading, self.config['prog_total'], \
                self._bytes_read, filesize)
        else:
            (read, read_prefix) = utils._byte_convert( self._bytes_read )
            message = "\rDownloading %-56s (%-7s%-1sB)" %\
                      (self._now_downloading[:27], read, read_prefix)
            progress = "Downloading %s %s %s" \
                %(self._now_downloading, self.config['prog_total'], \
                self._bytes_read)
        
        if self.log:
            self.log.write_tty(message)
            if TYPE == 1 and self._now_downloading[-3:] == 'rpm':
                self.log.write_progress(progress)


    def _do_download( self, uri, TYPE=1 ):
        scheme, host, path, param, query, fragment = urlparse.urlparse( uri )

        if '@' in host and self.auth_handler and scheme in ['http', 'https']:
            try:
                user_password, host = string.split(host, '@', 1)
                user, password = string.split(user_password, ':', 1)
                self.auth_handler.add_password(None, host, user, password)
            except ValueError, e:
                raise ex.auth_error, "Bad URL: %s" %url 


        uri = urlparse.urlunparse((scheme, host, path, param, query, fragment))
        # Make sure the cache is ready to accept the file.
        filename = os.path.normpath(os.path.join(self.cachedir, uri))
        basename = os.path.basename( uri )
        self._now_downloading = basename
        length = 61 - len(basename)
        tmpfilename = os.path.join( self.tmpdir, basename )

        try:
            blocksize = 1024*8
            self._download_callback(0, 0, 0, basename, TYPE)
            urlobj = self.opener.urlopen(uri)
            hdrs = urlobj.info()
            if hdrs.has_key('Content-Length'):
                size = int(hdrs["Content-Length"])
            else:
                size = -1
            self._download_callback(0, blocksize, size, basename)
            
            # Write the data to file named 'tmpfilename':
            fileobj = open(tmpfilename, 'wb')
            block = urlobj.read(blocksize)
            blocknum = 1
            self._download_callback(blocknum, blocksize, size, basename)
            while block:
                fileobj.write(block)
                block = urlobj.read(blocksize)
                blocknum += 1
                self._download_callback(blocknum, blocksize, size, basename)
            fileobj.close()

            # gunzip compressed files
            if tmpfilename[-3:] == '.gz':
                import gzip
                gfd = gzip.open(tmpfilename)
                localfilename = tmpfilename[:-3]
                fd = open(localfilename, 'wb')
                block = gfd.read(8192)
                while block:
                    fd.write(block)
                    block = gfd.read(8192)
                gfd.close()
                fd.close()
                del(gfd, fd)
                os.remove(tmpfilename)
            else:
                localfilename = tmpfilename
            if length < 0:
                basename = basename[:length]
                length = 0
            message = "\rDownloading %s - done" %basename +" "*length
            if self.log and not filename[-3:] in ['asc','md5']: 
                self.log.write_tty(message)
            return localfilename
        except (OSError,IOError), err:
            raise ex.download_error, err
        except socket.error, err:
            if self.log and err[0] == 4: #interrupted system call (Ctrl+C)
                self.log.write_tty('\n')
                raise KeyboardInterrupt
            else:
                raise
        except:
            raise


    def download( self, url, sigurl=None, CHECKSIG=1, TYPE=1):
        """Download a file and signature, check signature, move to cachedir.

        The argument is the url of the file. Optional argument is the url
        of the signature. The default value for the signature name is
        url.asc
        
        TYPE tells us where to put the cached files. 
        1 = rpms
        2 = rdfs
        """

        url = string.strip(url)
        # Check if the file exists - if it does, return
        if TYPE == 1:
            localurl = "rpms/" + url
        elif TYPE == 2:
            localurl = "rdfs/" + url
        if urlparse.urlparse(url)[0] == "":
            url = "file:" + url
            
        filename = os.path.normpath(os.path.join(self.cachedir, localurl))
        cachepath = os.path.dirname(filename)

        if os.path.exists(filename):
            # if we already have the file, don't download again...
            return filename

        if not os.path.isdir(cachepath):
            if os.path.exists(cachepath):
                os.remove(cachepath)
            os.makedirs(cachepath)

        # Actually download stuff
        if not sigurl:
            if url[-3:] == '.gz':
                sigurl = url[:-3] + SIGNATURE_APPEND
            else:
                sigurl = url + SIGNATURE_APPEND

        # Get the signature
        if CHECKSIG:
            try:
                signame = self._do_download( sigurl )
            except ex.auth_error, errmsg:
                host = urlparse.urlparse(sigurl)[1]
                raise ex.auth_error, "\nAuthentication failed for host %s:\n %s\n" % (host, errmsg)
            except ex.download_error, errmsg:
               raise ex.download_error, "\nDownload failed for %s:\n %s\n" % (sigurl, errmsg)

        # Get the file
        try:
            tmpfilename = self._do_download( url, TYPE )
        except ex.auth_error, errmsg:
            host = urlparse.urlparse(url)[1]
            raise ex.auth_error, "\nAuthentication failed for host %s:\n %s\n" % (host, errmsg)
        except ex.download_error, errmsg:
            raise ex.download_error, "\nDownload failed for %s:\n %s\n" % (url, errmsg)

        # Check the sig
        if CHECKSIG and tmpfilename and signame:
            retval, output = gpg.checksig(signame, self.gnupgdir, self.config['keyring'])
            os.remove(signame)
            
        # If we have come this far, we should have the correct file properly
        # downloaded. Time to move it...
        if tmpfilename:
            if not tmpfilename[:3] == filename[:3]:
                filename = filename[:-3]
            shutil.copy(tmpfilename, filename)
            os.remove(tmpfilename)
        else:
            filename = None


        # return just the filename - we don't really care about the output...
        return filename

