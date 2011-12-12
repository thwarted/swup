#!/usr/bin/env python
#  Copyright 2003 - 2004 Tor Hveem - <tor@bash.no>
#/$Id: rdf.py,v 1.18 2005/06/29 11:54:31 christht Exp $

import formatter, string, os, sys
from swuplib import utils

_XMLHEAD = '<?xml version="1.0" encoding="iso-8859-1"?>'
_RDFHEAD = '''<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
             xmlns:spi="http://www.trustix.net/schema/rdf/spi-0.0.1#">'''
_RDFEND = '</rdf:RDF>'


def escape_for_xml(data):
    data = string.replace(data, "&", "&amp;")
    data = string.replace(data, "<", "&lt;")
    data = string.replace(data, ">", "&gt;")
    return data




def escape_capabilityname(capabilityname):
    # Hack to escape / in requirements.
    # Example: /bin/bash -> #bin#bash
    capabilityname = string.replace(capabilityname, "_", "__")
    capabilityname = string.replace(capabilityname, "/", "_")
    return capabilityname




class writer(formatter.NullWriter):

    def __init__(self, file=None, maxcol=72, indent=4, wrapindent=2):
        self.file = file
        self.indent = indent
        self.wrapindent = wrapindent
        self.maxcol = maxcol
        formatter.NullWriter.__init__(self)
        self.reset()

    def set_fd(self, fd):
        self.file = fd

    def new_margin(self, margin, level):
        self.margin = level * self.indent
        self.col = self.margin

    def reset(self):
        self.atbreak = 0
        self.atlinestart = 1
        self.atlinewrap = 0
        self.margin = 0
        self.col = self.margin        

    def send_paragraph(self, blankline):
        self.file.write('\n'*blankline)
        self.col = self.margin
        self.atbreak = 0
        self.atlinewrap = 0
        self.atlinestart = 1
        
    def send_line_break(self):
        self.file.write('\n')
        self.col = self.margin
        self.atbreak = 0
        self.atlinestart = 1

    def send_literal_data(self, data):
        self.file.write(data)
        i = string.rfind(data, '\n')
        if i >= 0:
            self.col = self.margin
            data = data[i+1:]
        data = string.expandtabs(data)
        self.col = self.col + len(data)
        self.atbreak = 0
                
    def send_flowing_data(self, data):
        if not data: return
        atbreak = self.atbreak or data[0] in string.whitespace
        atlinestart = self.atlinestart
        atlinewrap = self.atlinewrap
        wrapindent = self.wrapindent
        margin = self.margin
        col = self.col
        maxcol = self.maxcol
        write = self.file.write
        for word in string.split(data):
            if atbreak:
                if col + len(word) >= maxcol:
                    write('\n')
                    col = margin
                    atlinewrap = 1
                    atlinestart = 1
                else:
                    write(' ')
                    atlinestart = 0
                    atlinewrap = 0
                    col = col + 1
            if atlinestart:
                #col = col + margin
                write(margin*' ')
                alinestart = 0
            if atlinewrap:
                #col = col + margin
                write((self.wrapindent)* ' ')
                atlinewrap = 0
            write(word)
            col = col + len(word)
            atbreak = 1
        self.atlinewrap = atlinewrap
        self.atlinestart = 0
        self.col = col
        self.atbreak = data[-1] in string.whitespace





class package_formatter:

    def __init__(self, writer, resources, resourcedirname, packagedirname,
                 packageprefix, sigprefix): 
        self.formatter = formatter.AbstractFormatter(writer)
        self.resourcedir = os.path.join('..', resourcedirname)
        self.resources = resources
        #self.packagedir = packagedir
        self.packageprefix = packageprefix
        self.sigprefix = sigprefix

    def reset(self):
        self.formatter.writer.reset()

    def set_fd(self, fd):
        self.formatter.writer.file = fd
        
    def format_head(self):
        f = self.formatter
        f.add_flowing_data(_XMLHEAD)
        f.end_paragraph(0)
        f.push_margin("left")
        f.add_flowing_data(_RDFHEAD)
        f.end_paragraph(0)

    def format_description(self):
        f = self.formatter
        text = self.pkgdata["description"]
        paras = string.split(text, '\n\n')
        f.add_flowing_data('<spi:description rdf:parseType="Litteral">')
        f.add_line_break()
        f.push_margin("left")
        for para in paras:
            f.add_flowing_data("<p>")
            f.add_flowing_data(escape_for_xml(para))
            f.add_flowing_data("</p>")
            f.add_line_break()
        f.add_line_break()
        f.pop_margin()
        f.add_flowing_data("</spi:description>")
        f.end_paragraph(0)
            
        f.end_paragraph(0)

    def format_requirements(self):
        f = self.formatter
        requirements = self.pkgdata["requirements"]
        if requirements == []:
            f.add_flowing_data("<spi:requires />")
            f.end_paragraph(0)
            return
        nitems = len(requirements)
        f.add_flowing_data("<spi:requires>")
        f.add_line_break()
        f.push_margin("left")
        f.add_flowing_data("<rdf:Bag>")
        f.add_line_break()
        f.push_margin("left")
        f.add_line_break()
        
        for requirement in requirements:
            reqname, reqrule = requirement
            reqrule = escape_for_xml(reqrule)
            try:
                reqaddress = self.resources[reqname]
                f.add_flowing_data('<rdf:li parseType="Resource">')
                f.add_line_break()
                f.push_margin("left")
                f.add_flowing_data('<spi:requirement>%s</spi:requirement>' %
                        reqrule)
                f.add_line_break()
                f.add_flowing_data(
                    '<spi:resource rdf:resource="%s" />' % reqaddress)
                f.add_line_break()
                f.pop_margin()
                f.add_flowing_data("</rdf:li>")
                f.add_line_break()
            except KeyError, errmsg:
                sys.stderr.write('Missing resource for package %s: %s\n' %\
                                 (self.pkgdata['basename'], reqname))
            except:
                raise

        f.pop_margin()
        f.add_flowing_data("</rdf:Bag>")
        f.add_line_break()
        f.pop_margin()
        f.add_flowing_data("</spi:requires>")
        f.end_paragraph(0)



    def format_conflicts(self):
        f = self.formatter
        conflicts = self.pkgdata["conflicts"]
        if not conflicts:
            f.add_flowing_data('<spi:conflicts />')
            f.end_paragraph(0)
            return

        f.add_flowing_data('<spi:conflicts>')
        f.add_line_break()
        f.push_margin("left")
        f.add_flowing_data('<rdf:Bag>')
        f.push_margin("left")

        for conflict in conflicts:            
            conflict = escape_for_xml(conflict)
            f.add_line_break()
            f.add_flowing_data("<rdf:li>%s</rdf:li>" % conflict)
        f.add_line_break()
        f.pop_margin()
        f.add_flowing_data("</rdf:Bag>")
        f.pop_margin()
        f.add_line_break()
        f.add_flowing_data("</spi:conflicts>")
        f.end_paragraph(0) 

    def format_rdf(self):
        f = self.formatter
        f.push_margin("left")

        if self.pkgdata.has_key('uri'):
            address = self.pkgdata['uri']
        else:
            if self.packageprefix:
                if utils.is_absolute(self.packageprefix):
                    address = '%s/%s' % (self.packageprefix, self.pkgdata["basename"])
                else:
                    address = os.path.join(self.packageprefix,
                                           self.pkgdata["basename"])
            else:
                address = os.path.join('../..', self.pkgdata["filename"])
        
        f.add_flowing_data('<rdf:Description rdf:about="%s">' % address)
        f.end_paragraph(0)
        f.push_margin("left")
        f.add_flowing_data('<spi:name>%s</spi:name>' % 
                                   self.pkgdata["name"])
        f.end_paragraph(0)
        if self.pkgdata['epoch']:
            f.add_flowing_data('<spi:epoch>%s</spi:epoch>' %
                                   self.pkgdata["epoch"])
            f.end_paragraph(0)
        f.add_flowing_data('<spi:version>%s</spi:version>' %
                                   self.pkgdata["version"])
        f.end_paragraph(0)
        f.add_flowing_data('<spi:package_type>%s</spi:package_type>' %
                                   self.pkgdata["package_type"])
        f.end_paragraph(0)
        f.add_flowing_data('<spi:release>%s</spi:release>' %
                                   self.pkgdata["release"])
        f.end_paragraph(0)
        f.add_flowing_data('<spi:arch>%s</spi:arch>' %
                                   self.pkgdata["arch"])
        f.end_paragraph(0)
        f.add_flowing_data('<spi:os>%s</spi:os>' %
                                   self.pkgdata["os"])
        f.end_paragraph(0)
        f.add_flowing_data('<spi:size>%s</spi:size>' % self.pkgdata["size"])
        f.end_paragraph(0)
        f.add_flowing_data('<spi:md5sum>%s</spi:md5sum>' % \
                           self.pkgdata["md5sum"])
        f.end_paragraph(0)
        if self.pkgdata["distribution"]:

            f.add_flowing_data('<spi:distribution>%s</spi:distribution>'
                               % escape_for_xml(self.pkgdata[\
                                                "distribution"]))
            f.end_paragraph(0)
        else:
            f.add_flowing_data('<spi:distribution />')
            f.end_paragraph(0)

        if self.pkgdata["vendor"]:
            f.add_flowing_data('<spi:vendor>%s</spi:vendor>'
                               % escape_for_xml(self.pkgdata["vendor"]))
            f.end_paragraph(0)
        else:
            f.add_flowing_data('<spi:vendor />')
            f.end_paragraph(0)
        if self.sigprefix:
            if utils.is_absolute(self.sigprefix):
                sigfile = '%s/%s' % (self.sigprefix, self.pkgdata["basename"] + ".asc")
            else:
                sigfile = os.path.join(self.sigprefix,
                                       self.pkgdata["filename"] + ".asc")
        else:
            sigfile = os.path.join('../..', self.pkgdata["filename"] +
                                   ".asc")
        
        f.add_flowing_data('<spi:signature rdf:resource="%s" />' % sigfile )
        f.end_paragraph(0)
        f.add_flowing_data('<spi:group>%s</spi:group>' %
                                   escape_for_xml(self.pkgdata["group"]))
        f.end_paragraph(0)
        f.add_flowing_data('<spi:build_date>%s</spi:build_date>' %
                           self.pkgdata["build_date"])

        f.end_paragraph(0)
        f.add_flowing_data('<spi:copyright>%s</spi:copyright>' %
                           escape_for_xml(self.pkgdata["copyright"]))
        f.end_paragraph(0)

        f.add_flowing_data('<spi:summary><p>%s</p></spi:summary>' %
                                   escape_for_xml(self.pkgdata["summary"]))
        f.end_paragraph(0)
        self.format_description()
        #self.format_changelog()
        obsoletes = self.pkgdata["obsoletes"]
        if not obsoletes:
            f.add_flowing_data('<spi:obsoletes />')
            f.end_paragraph(0)
        else:
            f.add_flowing_data('<spi:obsoletes>')
            f.end_paragraph(0)
            f.push_margin('left')
            f.add_flowing_data('<rdf:Bag>')
            f.end_paragraph(0)
            f.push_margin('left')
            for obs in obsoletes:
                f.add_flowing_data('<rdf:li>%s</rdf:li>' % obs)
                f.end_paragraph(0)
            f.pop_margin()
            f.add_flowing_data('</rdf:Bag>')
            f.end_paragraph(0)
            f.pop_margin()
            f.add_flowing_data('</spi:obsoletes>')
            f.end_paragraph(0)
        # FIXME!!
        self.format_requirements()
        self.format_conflicts()
        f.pop_margin()
        f.add_flowing_data("</rdf:Description>")
        f.end_paragraph(0)
        f.pop_margin()
        f.add_flowing_data("</rdf:RDF>")
        f.pop_margin()
        f.end_paragraph(0)
        
    def feed(self, pkgdata):
        self.pkgdata = pkgdata
        self.format_head()
        self.format_rdf()




class packagelist_formatter:

    def __init__(self, writer, packagedirname,
                 resourcelist_filename, outfile=None):
        self.packagedir = packagedirname
        #writer = rdf_writer(file=outfile)
        self.formatter = formatter.AbstractFormatter(writer)
        self.resourcelist_filename = resourcelist_filename
       
    def reset(self):
        self.formatter.writer.reset()

    def set_fd(self, fd):
        self.formatter.writer.file = fd
        
    def format_head(self):
        f = self.formatter
        f.add_flowing_data(_XMLHEAD)
        f.end_paragraph(0)
        f.push_margin("left")
        f.add_flowing_data(_RDFHEAD)
        f.end_paragraph(0)

    def format_description(self):
        f = self.formatter
        f.push_margin("left")
        f.add_flowing_data('<rdf:Description rdf:about="%s">'
                           % self.packagedir)
        f.end_paragraph(0)
        f.push_margin("left")
        f.add_flowing_data('<spi:resource_list_file rdf:resource="%s" />' %\
                           self.resourcelist_filename)
        f.end_paragraph(0)
        f.add_flowing_data('<spi:package_list>')
        f.end_paragraph(0)
        f.push_margin("left")
        f.add_flowing_data('<rdf:Bag>')
        f.end_paragraph(0)

    def format_package(self, packageinfo):
        name = packageinfo["name"]
        version = packageinfo["version"]
        release = packageinfo["release"]
        epoch = packageinfo["epoch"]
        group = packageinfo["group"]
        summary = packageinfo["summary"]
        obsoletes = packageinfo["obsoletes"]
        basename = packageinfo["basename"]

        f = self.formatter
        f.push_margin("left")
        f.add_flowing_data('<rdf:li rdf:parseType="Resource">')
        f.end_paragraph(0)
        f.push_margin("left")
        f.add_flowing_data('<spi:name>%s</spi:name>' % 
                           name)
        f.end_paragraph(0)
        if epoch:
            f.add_flowing_data('<spi:epoch>%s</spi:epoch>' % 
                           epoch)
            f.end_paragraph(0)
        f.add_flowing_data('<spi:version>%s</spi:version>' %
                           version)
        f.end_paragraph(0)
        f.add_flowing_data('<spi:release>%s</spi:release>' %
                           release)
        f.end_paragraph(0)
        if not obsoletes:
            f.add_flowing_data('<spi:obsoletes />')
            f.end_paragraph(0)
        else:
            f.add_flowing_data('<spi:obsoletes>')
            f.end_paragraph(0)
            f.push_margin('left')
            f.add_flowing_data('<rdf:Bag>')
            f.end_paragraph(0)
            f.push_margin('left')
            for obs in obsoletes:
                f.add_flowing_data('<rdf:li>%s</rdf:li>' % obs)
                f.end_paragraph(0)
            f.pop_margin()
            f.add_flowing_data('</rdf:Bag>')
            f.end_paragraph(0)
            f.pop_margin()
            f.add_flowing_data('</spi:obsoletes>')
            f.end_paragraph(0)

        #f.add_flowing_data('<spi:group>%s</spi:group>' %
        f.add_flowing_data('<spi:resource rdf:resource="%s.rdf" />'\
                           % os.path.join(self.packagedir, basename))
        f.end_paragraph(0)
        f.add_flowing_data('<spi:summary><p>%s</p></spi:summary>' % \
                           escape_for_xml(summary))
        f.end_paragraph(0)
        f.pop_margin()
        f.add_flowing_data('</rdf:li>')
        f.end_paragraph(0)
        f.pop_margin()


    def format_foot(self):
        f = self.formatter
        f.add_flowing_data('</rdf:Bag>')
        f.end_paragraph(0)
        f.pop_margin()
        f.add_flowing_data('</spi:package_list>')
        f.end_paragraph(0)
        f.pop_margin()
        f.add_flowing_data('</rdf:Description>')
        f.end_paragraph(0)
        f.pop_margin()
        f.add_flowing_data('</rdf:RDF>')
        f.end_paragraph(0)
        f.pop_margin()
        
        
    def format_body(self):
        pass

    def feed(self, packagedict):
        self.format_head()
        self.format_description()
        for packageinfo in packagedict.values():
            self.format_package(packageinfo)
        self.format_foot()




class resources_formatter:

    def __init__(self, writer, packagedirname, outfile=None):
        #writer = rdf_writer(outfile)
        self.formatter = formatter.AbstractFormatter(writer)
        self.packagedir = packagedirname

    def reset(self):
        self.formatter.writer.reset()

    def set_fd(self, fd):
        self.formatter.writer.file = fd
        
    def format_head(self):
        f = self.formatter
        f.add_flowing_data(_XMLHEAD)
        f.end_paragraph(0)
        f.push_margin("left")
        f.add_flowing_data(_RDFHEAD)
        f.end_paragraph(0)

    def format_body(self, capabilitydata):
        f = self.formatter
        f.push_margin("left")
        f.add_flowing_data('<rdf:Description rdf:about="resources">')
        f.end_paragraph(0)
        f.add_flowing_data('<spi:resources>')
        f.end_paragraph(0)
        f.add_flowing_data('<rdf:Bag>')
        f.end_paragraph(0)
        f.push_margin("left")
        for capname in capabilitydata.keys():
            hashlist = {}
            f.add_flowing_data('<rdf:li parseType="Resource">')
            f.end_paragraph(0)
            f.push_margin("left")
            f.add_flowing_data('<spi:name>%s</spi:name>' %capname)
            f.end_paragraph(0)
            f.add_flowing_data('<rdf:Bag>')
            f.end_paragraph(0)
            f.push_margin("left")
            providers = capabilitydata[capname]
            for provider in providers:
                if provider.has_key("uri"):
                    uri = provider["uri"]
                else:
                    uri = os.path.join(self.packagedir,
                                   (provider["basename"] + ".rdf"))
                name = provider["name"]
                version = provider["version"]
                release = provider["release"]
                epoch = None
                if provider.has_key("epoch"):
                     epoch = provider["epoch"]
                hash = "%s-%s-%s-%s-%s" \
                    %(name, version, release, epoch, uri)
                if hashlist.has_key(hash):
                    continue
                else:
                    hashlist[hash] = True
                f.push_margin("left")
                f.add_flowing_data('<rdf:li parseType="Provider">')
                f.push_margin("left")
                f.end_paragraph(0)
                f.add_flowing_data('<spi:name>%s</spi:name>' % name)
                f.end_paragraph(0)
                if epoch:
                    f.add_flowing_data('<spi:epoch>%s</spi:epoch>' % epoch)
                    f.end_paragraph(0)
                f.add_flowing_data('<spi:version>%s</spi:version>' % version)
                f.end_paragraph(0)
                f.add_flowing_data('<spi:release>%s</spi:release>' % release)
                f.end_paragraph(0)
                f.add_flowing_data('<spi:uri>%s</spi:uri>' % uri)
                f.end_paragraph(0)
                f.pop_margin()
                f.add_flowing_data('</rdf:li>')
                f.add_line_break()
                f.pop_margin()
            f.pop_margin()
            f.add_flowing_data('</rdf:Bag>')
            f.end_paragraph(0)
            f.pop_margin()
            f.add_flowing_data('</rdf:li>')
            f.end_paragraph(0)
        f.pop_margin()
        f.add_flowing_data('</rdf:Bag>')
        f.end_paragraph(0)
        f.add_flowing_data('</spi:resources>')
        f.end_paragraph(0)
        f.add_flowing_data('</rdf:Description>')
        f.end_paragraph(0)

    def format_foot(self):
        f = self.formatter
        f.add_flowing_data('</rdf:RDF>')
        f.end_paragraph(0)
        f.pop_margin()

    def feed(self, capabilitydata):
        self.format_head()
        self.format_body(capabilitydata)
        self.format_foot()

class resource_formatter:

    def __init__(self, writer, packagedirname, outfile=None):
        #writer = rdf_writer(outfile)
        self.formatter = formatter.AbstractFormatter(writer)
        self.packagedir = os.path.join('..', packagedirname)

    def reset(self):
        self.formatter.writer.reset()

    def set_fd(self, fd):
        self.formatter.writer.file = fd
        
    def format_head(self):
        f = self.formatter
        f.add_flowing_data(_XMLHEAD)
        f.end_paragraph(0)
        f.push_margin("left")
        f.add_flowing_data(_RDFHEAD)
        f.end_paragraph(0)

    def format_body(self, capability_name, capability_data_list):
        f = self.formatter
        f.push_margin("left")
        f.add_flowing_data('<rdf:Description rdf:ID="%s">'
                           % capability_name)
        f.end_paragraph(0)
        f.push_margin("left")
        f.add_flowing_data('<spi:provided_by>')
        f.end_paragraph(0)
        f.push_margin("left")
        f.end_paragraph(0)
        f.add_flowing_data('<rdf:Alt>')
        f.end_paragraph(0)
        for capability in capability_data_list:
            name = capability["name"]
            version = capability["version"]
            release = capability["release"]
            if capability.has_key("epoch"):
                 epoch = capability["epoch"]
            else:
                 epoch = None
            if capability.has_key("uri"):
                uri = capability["uri"]
            else:
                uri = os.path.join(self.packagedir,
                                   (capability["basename"] + ".rdf"))
            f.push_margin("left")
            f.add_flowing_data('<rdf:li parseType="Resource">')
            f.push_margin("left")
            f.end_paragraph(0)
            f.add_flowing_data('<spi:name>%s</spi:name>' % name)
            f.end_paragraph(0)
            if epoch:
                f.add_flowing_data('<spi:epoch>%s</spi:epoch>' % epoch)
                f.end_paragraph(0)
            f.add_flowing_data('<spi:version>%s</spi:version>' % version)
            f.end_paragraph(0)
            f.add_flowing_data('<spi:release>%s</spi:release>' % release)
            f.end_paragraph(0)
            f.add_flowing_data('<spi:resource rdf:resource="%s" />' % uri)
            f.add_line_break()
            f.pop_margin()
            f.add_flowing_data('</rdf:li>')
            f.add_line_break()
            f.pop_margin()
        f.add_flowing_data('</rdf:Alt>')
        f.add_line_break()
        f.pop_margin()
        f.add_flowing_data('</spi:provided_by>')
        f.add_line_break()
        f.pop_margin()
        f.add_flowing_data('</rdf:Description>')
        f.add_line_break()
        f.pop_margin()

    def format_foot(self):
        f = self.formatter
        f.add_flowing_data('</rdf:RDF>')
        f.end_paragraph(0)
        f.pop_margin()

    def feed(self, capabilityname, capabilitydata):
        self.format_head()
        self.format_body(capabilityname, capabilitydata)
        self.format_foot()


class resourcelist_formatter:
    def __init__(self, writer, resourcedirname):
        #writer = rdf_writer(outfile)
        self.formatter = formatter.AbstractFormatter(writer)
        self.resourcedirname = resourcedirname
        
    def reset(self):
        self.formatter.writer.reset()

    def set_fd(self, fd):
        self.formatter.writer.file = fd
        
    def format_head(self):
        f = self.formatter
        f.add_flowing_data(_XMLHEAD)
        f.end_paragraph(0)
        f.push_margin("left")
        f.add_flowing_data(_RDFHEAD)
        f.end_paragraph(0)
        
    def format_resource(self, capfilenames):
        f = self.formatter
        f.push_margin("left")
        f.add_flowing_data('<rdf:Description rdf:about="%s">' % \
                           self.resourcedirname)
        f.end_paragraph(0)
        f.push_margin("left")
        f.add_flowing_data('<spi:resource_list>')
        f.end_paragraph(0)
        f.push_margin("left")
        f.add_flowing_data('<rdf:Bag>')
        f.end_paragraph(0)
        f.push_margin("left")
        for cap in capfilenames.keys():
            f.add_flowing_data('<rdf:li parseType="Resource">')
            f.add_flowing_data(\
                '<spi:resource spi:name="%s" rdf:resource="%s" />' %\
                (cap, capfilenames[cap]))
            f.add_flowing_data('</rdf:li>')
            f.end_paragraph(0)
        f.pop_margin()
        f.add_flowing_data('</rdf:Bag>')
        f.end_paragraph(0)
        f.pop_margin()
        f.add_flowing_data('</spi:resource_list>')
        f.pop_margin()
        f.end_paragraph(0)
        f.add_flowing_data('</rdf:Description>')
        f.pop_margin()
        f.end_paragraph(0)
    
    def format_foot(self):
        f = self.formatter
        f.add_flowing_data('</rdf:RDF>')
        f.end_paragraph(0)
        f.pop_margin()

    def feed(self, capfilenames):
        self.format_head()
        self.format_resource(capfilenames)
        self.format_foot()
    



class filelist_formatter:
    def __init__(self, packagedirname):
        self.packagedirname = packagedirname
        
    def reset(self):
        pass
        #self.formatter.writer.reset()

    def set_fd(self, fd):
        #self.formatter.writer.file = fd
        self.file = fd

    def feed(self, filelists):
        for key in filelists.keys():
            self.file.write('[%s]\n' % os.path.join(self.packagedirname,
                                                    key+'.rdf'))
            for file in filelists[key]:
                self.file.write(file + '\n')

