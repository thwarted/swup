#!/usr/bin/env python
# $Id: download.py,v 1.20 2001/06/28 11:26:42 olafb Exp $

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

import sys, time, os, urlparse, string, re, shutil
import gpg
import urllib

DEBUG = 0

# some constants/defaults
CACHEDIR = '/var/cache/swup'
TMPDIR = '/var/spool/swup/tmp'
SIGNATURE_APPEND = '.asc'
false, true = 0, 1

# define some exceptions
class DownloadException(Exception): pass
class FlushCacheException(DownloadException): pass
class SignatureException(DownloadException): pass
class AuthException(DownloadException): pass



def byte_convert( bytes ):
    """Returns a two tuple (<str>, <prefix>), where prefix is one of
    '', 'k' or 'M'."""
    div = bytes/float(1024)
    if div < 1:
        return (str(bytes), '')
    if div < 1024:
        return ( "%4.2f" %div, 'k')
    else:
        div = bytes / float(1024**2)
        return ("%4.2f" %div, 'M')



class download:

    def __init__( self, log, cachedir=CACHEDIR, tmpdir=TMPDIR):
        self.log = log
	self.cachedir = cachedir
	self.tmpdir = tmpdir
        self.opener = None
	if not os.path.isdir( tmpdir ):
            try:
                if os.path.exists( tmpdir ):
                    os.remove( tmpdir )
                os.makedirs( tmpdir )
            except (OSError, IOError), err:
                raise DownloadException, err

    def flush_cache( self ):
	urllib.urlcleanup()
	try:
	    if os.path.isdir(self.cachedir):
                for subdir in ['file:', 'http:', 'https:', 'ftp:']:
                    dir = os.path.join(self.cachedir, subdir)
                    if os.path.isdir(dir):
                        shutil.rmtree(dir)
                        os.mkdir(dir, 0755)
	except:
	    raise self.FlushCacheException, "Unable to flush cache."


    def callback(self, blocknum, blocksize, filesize):
        #if size == -1: don't use size in calculation.

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
                (speed, speed_prefix) = byte_convert( self._bytes_read/
                                                      float(self._time_used))
            else:
                speed, speed_prefix = 0, 'k'
            
            (size, size_prefix) = byte_convert( filesize )
            (read, read_prefix) = byte_convert( self._bytes_read )
            message = "\rDownloading "\
                      "%-24s (%-7s%-1sb of %-7s%-1sb, %-3d%%, %-7s%-1sb/s)"%\
                      (self._now_downloading[:21]+"...", read, read_prefix,
                       size, size_prefix, percent, speed, speed_prefix)
        else:
            (read, read_prefix) = byte_convert( self._bytes_read )
            message = "\rDownloading %-56s (%-7s%-1sb)" %\
                      (self._now_downloading[:27], read, read_prefix)
        
        self.log.write_tty(message)


    def _do_download( self, uri ):
        scheme, host, path, param, query, fragment = urlparse.urlparse( uri )
	if (not scheme == "file") and ("@" in host):
            raise AuthException, 'Authentication not supported.'

        # Make sure the cache is ready to accept the file.
	filename = os.path.normpath(os.path.join(self.cachedir, uri))
	cachepath = os.path.dirname(filename)
	if not os.path.isdir(cachepath):
	    if os.path.exists(cachepath):
		os.remove(cachepath)
            os.makedirs(cachepath)

        basename = os.path.basename( uri )
        self._now_downloading = basename
	tmpfilename = os.path.join( self.tmpdir, basename )
        try:
            (retrfile, headers) = urllib.urlretrieve( uri, tmpfilename,
                                                       self.callback )
        except KeyboardInterrupt:
            raise
        except IOError, err:
            raise DownloadException, err
        except:
            err, val = sys.exc_info()[:2]
            raise DownloadException, "%s: %s" % (err, val)

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
            
	return localfilename


    def download( self, url, sigurl=None, CHECKSIG=1):
	"""Download a file and signature, check signature, move to cachedir.

	The argument is the url of the file. Optional argument is the url
	of the signature. The default value for the signature name is
	url.asc"""

	# Check if the file exists - if it does, return
	if urlparse.urlparse(url)[0] == "":
	    url = "file:" + url
	filename = os.path.normpath(os.path.join(self.cachedir, url))
	cachepath = os.path.dirname(filename)

	if os.path.exists(filename):
	    # if we already have the file, don't download again...
	    return filename

	if not os.path.isdir(cachepath):
	    if os.path.exists(cachepath):
		os.remove(cachepath)
            os.makedirs(cachepath)

	# Actually download stuff
	if sigurl == None:
            if url[-3:] == '.gz':
                sigurl = url[:-3] + SIGNATURE_APPEND
            else:
                sigurl = url + SIGNATURE_APPEND

        # Get the signature
        if CHECKSIG:
            try:
                signame = self._do_download( sigurl )
            except AuthException, errmsg:
                host = urlparse.urlparse(sigurl)[1]
                raise AuthException, "Authentication failed for host %s: %s" % (host, errmsg)
            except DownloadException, errmsg:
                raise DownloadException, "Download failed for %s: %s" % (sigurl, errmsg)

        # Get the file
        try:
            tmpfilename = self._do_download( url )
        except AuthException, errmsg:
            host = urlparse.urlparse(url)[1]
            raise AuthException, "Authentication failed for host %s: %s" % (host, errmsg)
        except DownloadException, errmsg:
            raise DownloadException, "Download failed for %s: %s" % (url, errmsg)

	# Check the sig
        if CHECKSIG:
            try:
                retval, output = gpg.checksig(signame)
                os.remove(signame)
            except gpg.signature_fail:
                raise SignatureException, sys.exc_info()[1]
            
	# If we have come this far, we should have the correct file properly
	# downloaded. Time to move it...
        shutil.copy(tmpfilename, filename)
        os.remove(tmpfilename)


	# return just the filename - we don't really care about the output...
	return filename


