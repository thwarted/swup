#!/usr/bin/python
import os
import cgi
import string
import sys
import re


title = "SWUP Web Search Engine"

baseurl = '/~swup/cgi-bin/swup_query.py'
mainurlbase = 'http://http.trustix.org/pub/trustix/releases/'
contriburlbase = 'http://http.trustix.org/pub/contrib/'
localheaders = ""
default_target = "trustix-2.2"
default_operation = "--search-package"

allowed_targets = [ 'trustix-2.2',
                    'trustix-3.0',
                    'community-2.2',
                    'community-3']

package_operations = ['--search-package','--search-file','--what-provides']
allowed_operations = package_operations + ['--search-resource','--describe']

#
# Get site specific variables:
#
if os.path.isfile(os.path.join(os.curdir,'swup_query_config.py')):
    sys.path.append( os.curdir )
    from swup_query_config import *

#
# Make sure we have working defaults:
#
if not default_target in allowed_targets:
    default_target = allowed_targets[0]

if not default_operation in allowed_operations:
    default_operations = allowed_operations[0]

page = """content-type: text/html

<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
<HTML>
<HEAD>
<META HTTP-EQUIV="CONTENT-TYPE" CONTENT="text/html; charset=iso-8859-1">
<TITLE>%s</TITLE>
<META NAME="GENERATOR" CONTENT="swup">
%s
</HEAD>
<BODY>
""" %(title, localheaders)
print page


# Get form data
# Leave out the "keep_blank_values" bit to filter out empty fields
form = cgi.FieldStorage()
regexp = ""
object = ""
targets = []
operations = []

for target in allowed_targets:
    if form.has_key(target):
        targets.append(target)

if not targets:
    targets.append(default_target)

for operation in allowed_operations:
    if form.has_key(operation):
        operations.append(operation)

if not operations:
    operations.append(default_operation)

if form.has_key('regexp'):
    minifs = form['regexp']
    regexp = minifs.value
if form.has_key('--describe'):
    minifs = form['--describe']
    object = minifs.value
if form.has_key('--what-provides'):
    minifs = form['--what-provides']
    object = minifs.value


checked_22 = ""
checked_c_22 = ""
checked_30 = ""
checked_c_3 = ""
if "trustix-2.2" in targets:
    checked_22 = "checked"
if "community-2.2" in targets:
    checked_c_22 = "checked"
if "trustix-3.0" in targets:
    checked_30 = "checked"
if "community-3" in targets:
    checked_c_3 = "checked"

checked_package = ""
checked_file = ""
checked_resource = ""
if "--search-package" in operations:
    checked_package = "checked"
if "--search-file" in operations:
    checked_file = "checked"
if "--search-resource" in operations:
    checked_resource = "checked"

content  = """
<h1>%s</h1>
<P>
Please select search parameters:

<form action="%s" method="post" accept-charset="iso-8859-1">
<strong>Search term:</strong><br />
<input type="text" name="regexp" value="%s" tabindex="0" size="40"><br />
<hr>
<strong>Search repositories:</strong><br />
<input type="checkbox" name="trustix-2.2" value="yes" %s>Trustix Secure Linux 2.2<br />
<input type="checkbox" name="community-2.2" value="yes" %s>Community Contrib for 2.2<br />
<input type="checkbox" name="trustix-3.0" value="yes" %s>Trustix Secure Linux 3.0<br />
<input type="checkbox" name="community-3" value="yes" %s>Community Contrib for 3.X<br />
<hr>
<strong>Search targets:</strong><br />
<input type="checkbox" name="--search-package" value="yes" %s>Search package names<br />
<input type="checkbox" name="--search-file" value="yes" %s>Search file names<br />
<input type="checkbox" name="--search-resource" value="yes" %s>Search resource names<br />
<input type="submit" value="Search">
</form>
</P>
""" %(title, baseurl, regexp, checked_22, checked_c_22, checked_30, checked_c_3, checked_package, checked_file, checked_resource)
print content

#
# Handle special case with regexps and various operations:
#
if regexp and "--search-file" in operations:
    if not re.search("[a-zA-Z].*[a-zA-Z]+",regexp):
        print "<strong>You need at least two characters in your search term " +\
                "to perform valid file search.</strong>"
        regexp = ""
if regexp and "--search-file" in operations and regexp[0] == "/":
    regexp = "^%s" %regexp

if regexp:
    print "<strong>Search results:</strong><br />"
elif object:
    regexp = object
            

if regexp:
    for target in targets:
        if target[:7] == "trustix":
            uri = "%s/%s/i586/trustix/rdfs/" %(mainurlbase,target)
        else:
            uri = " %s/%s/i586/rdfs/ " %(contriburlbase,target)
        print "<br /><br /><strong>Match(es) on '%s' in %s:<br /></strong>" %(regexp, target)
        print "<hr>"
        for operation in operations:
            index = 0
            command = "swup --repository-URI %s %s '%s'" %(uri,operation,regexp)
            fd = os.popen(command)
            line = fd.readline()
            if not line:
                print "<strong>Got %s matches from '%s'<br /></strong>" %(index, operation)
            	print "<hr>"
                continue
            print "<strong>Match(es) from %s:<br /></strong>" %operation
            while(line):
                line = string.strip(line)
                if line:
                    if line[:10] == "[cmdline] ":
                        line = line[10:]
                    if operation in package_operations:
                        words = string.split(line)
                        package = words[0]
                        url = "<a href=\"%s?--describe=%s&%s=yes\">%s</a>" %(baseurl,package,target,package)
                        words[0] = url
                        line = ""
                        for word in words:
                            line += "%s " %word
                    elif operation == "--search-resource":
                        url = "<a href=\"%s?--what-provides=%s&%s=yes\">%s</a>" %(baseurl,line,target,line)
                        line = url
                    print "%s\n</br />\n" %line
                    index += 1
                line = fd.readline()
            fd.close()
            if operation == "--describe":
                index = 1
            if regexp:
                print "<strong>Got %s match(es) from '%s'<br /></strong>" %(index, operation)
            	print "<hr>"
print "</body>\n</html>"
