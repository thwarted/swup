# -*- python -*-
# $Id: utils.py,v 1.3 2001/03/20 11:40:18 olafb Exp $
    
"""utils.py
Contains misc. utility functions used by other main modules."""

import re, string, urlparse, os




#alphabet_regexp = re.compile("[a-zA-Z]+")
nonnum_regexp = re.compile("\D+")




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
    f = open(filename, 'r')
    for line in f.readlines():
        m.update(line)
    f.close()
    return hexify(m.digest())




def alphanum_split(instr):
    """Split groups of alphabetic and integer characters in a string into
    a list of strings and integers."""
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




def list2d_cmp(list0, list1):
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

    

def version_cmp((ver0,rel0), (ver1, rel1)):
    """Compare two (<version string>, <release string>)-tuples.
    Returns 1 if the first is greater, 0 if they are equal, and -1 if the
    first is smaller."""

    # Hack to replace '_' with '.' in version strings.
    ver0 = string.replace(ver0, "_", ".")
    ver1 = string.replace(ver1, "_", ".")
    ver0 = string.split(ver0, ".")
    ver1 = string.split(ver1, ".")

    for i in range(len(ver0)):
        ver0[i] = alphanum_split(ver0[i])
    for i in range(len(ver1)):
        ver1[i] = alphanum_split(ver1[i])


    # compare versions:
    result = list2d_cmp(ver0, ver1)
    # If versions were equal, compare release
    if result == 0:
        rel0 = string.replace(rel0, "_", ".")
        rel1 = string.replace(rel1, "_", ".")
        rel0 = string.split(rel0, ".")
        rel1 = string.split(rel1, ".")

        for i in range(len(rel0)):
            rel0[i] = alphanum_split(rel0[i])
        for i in range(len(rel1)):
            rel1[i] = alphanum_split(rel1[i])
        result = list2d_cmp(rel0, rel1)
    return result


def normalize_uri(uri):
    "Normalize an uri. Returns uri without ../-es."
    protocol, server, path, param, query, fragment = urlparse.urlparse(uri)
    path = os.path.normpath(path)
    return urlparse.urlunparse((protocol, server, path, param, query,
                                fragment))
    




