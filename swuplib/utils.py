# -*- python -*-
# $Id: utils.py,v 1.24 2005/06/13 11:12:53 christht Exp $

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
    
"""utils.py
Contains misc. utility functions used by other main modules."""

import re, string, urlparse, os, md5, gzip


hexStr = string.hexdigits
def hexify(str):
    "Turn a string of non-printable chars. into a string of hex chars."
    r = ''
    for ch in str:
        i = ord(ch)
        r = r + hexStr[(i >> 4) & 0xF] + hexStr[i & 0xF]
    return r

def md5sum(filename):
    "Return the hex-char. md5sum for file given by filename."
    m = md5.new()
    try:
        test = m.hexdigest()
        f = open(filename, 'r')
        m.update(f.read())
        f.close()
        return m.hexdigest()
    except Exception:
        f = open(filename, 'r')
        for line in f.readlines():
            m.update(line)
        f.close()
        return hexify(m.digest())
    except:
        raise

def md5sumtofile(filename):
    "Give a filename, creates a filename.md5 containing the md5 sum"
    md5outfilename = filename + ".md5"
    md5data = md5sum(filename)+"  "+os.path.basename(filename)+"\n"
    fd = open(md5outfilename, 'w') 
    fd.write(md5data)
    fd.close()


def normalize_uri(uri):
    "Normalize an uri. Returns uri without ../-es."
    protocol, server, path, param, query, fragment = urlparse.urlparse(uri)
    path = os.path.normpath(path)
    return urlparse.urlunparse((protocol, server, path, param, query,
                                fragment))
    
def _byte_convert(bytes):
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


def is_absolute(uri):
    if re.compile("(^http:)|(^ftp:)|(^file:)").match(uri):
        return True

def compress_file(filename,deletefile=None):
    """Compresses argument file to file.gz withouth deleting file"""
    try:
        gzfilename = filename+".gz"
        gfd = gzip.open(gzfilename, 'wb')
        fd = open(filename, 'r')
        block = fd.read(8192)
        while block:
            gfd.write(block)
            block = fd.read(8192)
        gfd.close()
        fd.close()
        del(gfd, fd)
        if deletefile:
            os.remove(filename)
    except:
        raise

