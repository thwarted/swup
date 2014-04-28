#! /usr/bin/env python

# $Id: spiparser.py,v 1.4 2001/06/19 11:59:18 olafb Exp $

import xmllib, sys, string, types, os, re, utils

# Exceptions
parse_error = "spiparser.parse_error"

RDF_XMLNS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
SPI_XMLNS = "http://www.trustix.net/schema/rdf/spi-0.0.1#"

RDF_RDF_ELEMENT = RDF_XMLNS + " RDF"
RDF_DESCRIPTION_ELEMENT = RDF_XMLNS + " Description"
SPI_LIST_ELEMENT = RDF_XMLNS + " li"

SPI_COMPLEX_ELEMENTS = [ 
    SPI_XMLNS + " package_list",
    SPI_XMLNS + " requires",
    SPI_XMLNS + " conflicts",
    SPI_XMLNS + " provided_by",
    SPI_XMLNS + " obsoletes"]

SPI_LEAF_ELEMENTS = [
    SPI_XMLNS + " name",
    SPI_XMLNS + " version",
    SPI_XMLNS + " package_type",
    SPI_XMLNS + " release",
    SPI_XMLNS + " arch",
    SPI_XMLNS + " os",
    SPI_XMLNS + " distribution",
    SPI_XMLNS + " vendor",
    SPI_XMLNS + " packager",
    SPI_XMLNS + " sign_key_id",
    SPI_XMLNS + " sign_key_fingerprint",
    SPI_XMLNS + " group",
    SPI_XMLNS + " size",
    SPI_XMLNS + " build_date",
    SPI_XMLNS + " build_host",
    SPI_XMLNS + " copyright",
    SPI_XMLNS + " changelog",
    SPI_XMLNS + " description",
    SPI_XMLNS + " summary",
    SPI_XMLNS + " requirement",
    SPI_XMLNS + " signature",
    SPI_XMLNS + " source_code",
    SPI_XMLNS + " resource",
    SPI_XMLNS + " requirement"]
#    SPI_XMLNS + " package_list"]

RDF_COLLECTION_ELEMENTS = [
    RDF_XMLNS + " Alt",
    RDF_XMLNS + " Bag",
    RDF_XMLNS + " Seq"
    ]

XML_SIMPLE_ELEMENTS = ['p']

OPERATOR_REGEXP = re.compile(r'[<>=]+')
WHITESPACE_REGEXP = re.compile('\s*')



def split_requirement( requirement ):
    """split_requirement( requirement )
    Split a requirement string in the form
        '<name> <operator> <version string>'
    into a tuple of
        (<name>, <operator>, <version>, <release>)."""

    operator, version, release = [""]*3

    match_object = OPERATOR_REGEXP.search( requirement )
    
    if match_object:
        operator = match_object.group()
        name, version_string = OPERATOR_REGEXP.split(requirement)
        name = string.strip(name)
        version_string = string.strip(version_string)
        version_split = string.split(version_string, "-")
        version = version_split[0]
        if len(version_split) > 1:
            release = version_split[1]
    else :
        name = string.strip(requirement)

    return (name, operator, version, release)




class storage_node:
    def __init__(self, parent=None):
        self.parent = parent
        self.attr = None
        self.value = None
        self.children = None
        



class spi_handler(xmllib.XMLParser):

    def __init__(self):
        xmllib.XMLParser.__init__(self)
        self.buffer = ""
        self.elements = {}
        self.elements[RDF_DESCRIPTION_ELEMENT] = (
            self.handle_leaf_starttag,
            self.handle_leaf_endtag)

        for element in SPI_LEAF_ELEMENTS:
            self.elements[element] = (self.handle_leaf_starttag,
                                      self.handle_leaf_endtag)
        for element in RDF_COLLECTION_ELEMENTS:
            self.elements[element] = (self.handle_collection_starttag,
                                      self.handle_collection_endtag)

	for element in XML_SIMPLE_ELEMENTS:
	    self.elements[element] = (self.handle_simple_starttag,
	                              self.handle_simple_endtag)

        self.elements[SPI_LIST_ELEMENT] = (self.handle_rdf_li_starttag,
                                           self.handle_rdf_li_endtag)
        for element in SPI_COMPLEX_ELEMENTS:
            self.elements[element] = (self.handle_node_starttag,
                                      self.handle_node_endtag)

           
    def handle_simple_starttag(self, tag, attr):
	pass

    def handle_simple_endtag(self, tag):
	pass
	 
    def handle_leaf_starttag(self, tag, attr):
        #print "starttag: ", tag
        self.flush()
        newnode = storage_node(parent=self.node)
        if self.node.children == None:
            self.node.children = {}
        self.node.children[tag] = newnode
        self.node = newnode
        self.node.attr = attr
        
    def handle_leaf_endtag(self, tag):
        self.node.value = self.buffer
        #print self.buffer
        self.flush()
        self.node = self.node.parent
        #print "endtag: ", tag

    def handle_node_starttag(self, tag, attr):
        self.flush()
        newnode = storage_node(parent=self.node)
        if self.node.children == None:
            self.node.children = {}
        self.node.children[tag] = newnode
        self.node = newnode
        self.node.attr = attr

    def handle_node_endtag(self, tag):
        self.flush()
        self.node = self.node.parent

    def handle_collection_starttag(self, tag, attr):
        self.flush()
        newnode = storage_node(parent=self.node)
        if self.node.children == None:
            self.node.children = {}
        self.node.children[tag] = newnode
        self.node = newnode
        self.node.attr = attr

    def handle_collection_endtag(self, tag):
        self.flush()
        self.node = self.node.parent


    def handle_rdf_li_starttag(self, tag, attr):
        self.flush()
        parse_type = "Litteral" # The default
        if attr.has_key(RDF_XMLNS + " parseType"):
            parse_type = attr[RDF_XMLNS + " parseType"]
        newnode = storage_node(parent=self.node)
        self.parse_type = parse_type
        newnode.attr = attr
        if type(self.node.children ) != types.DictType:
            self.node.children = {}
        elementname = "rdf:RDF_%s" % (len(self.node.children) +1)
        self.node.children[elementname] = newnode
        self.node = newnode
        
    def handle_rdf_li_endtag(self, tag):
        if not self.parse_type == "Resource":
            #print "debug: buffer is %s" % self.buffer
            self.node.value = self.buffer
        self.node = self.node.parent
        self.flush()
        
    def handle_xml(self, encoding, standalone):
        self.flush()
        self.node = storage_node()

    def handle_doctype(self, tag, pubid, syslit, data):
        self.flush()

    def handle_entity(self, name, strval, pubid, syslit, ndata):
        self.flush()
        
    def handle_starttag(self, tag, method, attributes):
        tag = string.replace(tag, SPI_XMLNS + " ", "spi:")
        tag = string.replace(tag, RDF_XMLNS + " ", "rdf:")
        #print "start tag: %s" % tag
        tmpattrs = {}
        for key in attributes.keys():
            tmpkey = string.replace(key, RDF_XMLNS + " ", "rdf:")
            tmpattrs[tmpkey] = attributes[key]
        attributes = tmpattrs
        del tmpattrs
        method(tag, attributes)
        
    def handle_endtag(self, tag, method):
        tag = string.replace(tag, SPI_XMLNS + " ", "spi:")
        tag = string.replace(tag, RDF_XMLNS + " ", "rdf:")
        #print "end tag: %s" % tag
        method(tag)

    def handle_data(self, data):
        #print "handle_data: %s" % data
	data_list = WHITESPACE_REGEXP.split( data )
        data = string.lstrip(string.join( data_list, " " ) )
	#data = string.strip( string.join( data_list, " " ) )
        self.buffer = self.buffer + data

    def flush(self):
        self.buffer = ""

    def handle_paragraph(self, data):
	self.buffer = self.buffer + data

    def handle_cdata(self, data):
	#print "handle_cdata"
        self.buffer = self.buffer + data
        
    def handle_proc(self, name, data):
        pass
        #print 'processing:',name,`data`

    def handle_comment(self, data):
        pass

    #def syntax_error(self, message):
        #print 'error at line %d:' % self.lineno, message
    #    pass
    
    def unknown_starttag(self, tag, attrs):
        #print "unknown_starttag(self, %s, %s)" % (tag, attrs)
	self.flush()

    def unknown_endtag(self, tag):
        self.flush()

    def unknown_entityref(self, ref):
        pass

    def unknown_charref(self, ref):
        #print "unknown_charref. %s" % ref
	pass
    
    def close(self):
        xmllib.XMLParser.close(self)
        self.flush()

    def get_data(self):
        #print self.node.children
        return self.node




class rdf_reader:
    def __init__( self ):
        self.parser = spi_handler()

    def __del__( self ):
        del( self.parser )

    def read_rdf( self, filename ):
        file = open( filename, "r" )
        self.parser.reset()
        while 1:
            data = file.readline()
            if not data: break
            self.parser.feed( data )
        node = self.parser.get_data()
        #self.parser.close()
        file.close()
        del(data)
        return node


    def read_package_short( self, filename, baseuri ):
        node = self.read_rdf( filename )
        dict = {}
        
        if node.children == None:
            raise parse_error, "Unable to parse file %s" % filename
            
        try:

            uri = node.children["rdf:Description"].attr["rdf:about"]
            uri = utils.normalize_uri( os.path.join(baseuri, uri) )

            dict["uri"] = uri
            description = node.children["rdf:Description"].children
            dict["name"] = description["spi:name"].value
            #print "debug: name is", description["spi:name"].value
            dict["version"] = description["spi:version"].value

            dict["release"] = description["spi:release"].value

            obsoletes = []
            if description.has_key("spi:obsoletes"):
                obs_node = description["spi:obsoletes"].children
                if obs_node:
                    for li in obs_node["rdf:Bag"].children.values():
                        obsoletes.append(li.value)

            dict["obsoletes"] = obsoletes

        except KeyError:
            raise parse_error, "Unable to parse file '%s'" % uri

        return dict
    
    
    def read_package( self, filename, baseuri ):
        """read_package_rdf(filename)
        Parse package rdf file given by <filename>. Returns a dictionary with
        the rdf-elements as keys."""
        node = self.read_rdf( filename )

        try:
            description_node = node.children["rdf:Description"]
            version = description_node.children["spi:version"].value
            release = description_node.children["spi:release"].value
            arch = description_node.children["spi:arch"].value
            opsys = description_node.children["spi:os"].value
            group = description_node.children["spi:group"].value
            name = description_node.children["spi:name"].value
            pkg_uri = description_node.attr["rdf:about"]
            pkg_uri = utils.normalize_uri( os.path.join(baseuri, pkg_uri) )

            sig_uri = description_node.children["spi:signature"].attr[\
                "rdf:resource"]
            sig_uri = utils.normalize_uri( os.path.join(baseuri, sig_uri) )

            #requires = [] # a list containing all requirements
            requires_node = description_node.children["spi:requires"]

            requires_list = []
            if requires_node.children != None:
                requires_node = node.children["rdf:Description"].children[\
                        "spi:requires"].children["rdf:Bag"]

                for require_node in requires_node.children.values():
                    requirement = require_node.children[\
                        "spi:requirement"].value
                    resource_uri = require_node.children[\
                        "spi:resource"].attr["rdf:resource"]
                    resource_uri = utils.normalize_uri(
                        os.path.join(baseuri, resource_uri) )
                    requirement = split_requirement( requirement )
                    #print "debug: requirement ", requirement
                    requires_list.append( {"name": requirement[0],
                                           "operator": requirement[1],
                                           "version": requirement[2],
                                           "release": requirement[3],
                                           "uri": resource_uri} )
            conflicts = []
            if description_node.children.has_key( "spi:conflicts" ):
                conflicts_node = description_node.children["spi:conflicts"]
                if conflicts_node.children:
                    nodes = conflicts_node.children[\
                        "rdf:Bag"].children.values()
                    for node in nodes:
                        #print "debug: conflict %s %s" % ( name, node.value )
                        conflicts.append( node.value )
                else:
                    if conflicts_node.value:
                        conflicts.append( conflicts_node.value )
                        
                    
        except KeyError:
            raise parse_error, "Unable to parse file : '%s'" % filename

        return {"name":name,
                "version":version,
                "release":release,
                "group":group,
                "arch": arch,
                "os": opsys,
                "uri": pkg_uri,
                "signature": sig_uri,
                "requirements": requires_list,
                "conflicts": conflicts}


    def read_resource( self, filename, baseuri ):
        """read_resource_rdf( filename, baseuri)
        Parse resource rdf file given by <filename>.
        Returns a list of dictionaries with the rdf-elements as keys."""

        node = self.read_rdf( filename )    
        try:
            provided_by_node = node.children["rdf:Description"].children[\
                "spi:provided_by"]
            alt_node = provided_by_node.children["rdf:Alt"]

            resource_list = []
            for resource_node in alt_node.children.values():
                uri = resource_node.children["spi:resource"].attr[\
                    "rdf:resource"]
                uri = utils.normalize_uri( os.path.join(baseuri, uri) )
                version = resource_node.children["spi:version"].value
                release = resource_node.children["spi:release"].value
                name = resource_node.children["spi:name"].value
                resource_list.append( {"uri": uri,
                                       "name": name,
                                       "version": version,
                                       "release": release} )
        except KeyError:
            raise parse_error, "Unable to parse file : '%s'" % filename

        return resource_list


    
    def read_latest( self, filename, baseuri ):
        packagedict = {}
        topnode = self.read_rdf( filename )
        if topnode.children == None:
            raise parse_error, "Unable to parse file '%s'" % filename
        try:
            latest_nodes = topnode.children["rdf:Description"].children[\
                "spi:package_list"].children["rdf:Bag"].children.values()
            protocol_regexp = re.compile("(^http:)|(^ftp:)|(^file:)")

            for node in latest_nodes:
                name = node.children["spi:name"].value
                version = node.children["spi:version"].value
                release = node.children["spi:release"].value
                summary = node.children["spi:summary"].value
                resource = node.children["spi:resource"].attr["rdf:resource"]
                if not protocol_regexp.match(resource):
                    resource = os.path.join(baseuri, resource)
                    resource = utils.normalize_uri(resource)

                obsoletes = []
                if node.children.has_key("spi:obsoletes"):
                    obs_node = node.children["spi:obsoletes"].children
                    if obs_node:
                        for li in obs_node["rdf:Bag"].children.values():
                            obsoletes.append(li.value)
                    
                packagedict[name] = {
                    "name": name,
                    "version": version,
                    "release": release,
                    "obsoletes": obsoletes,
                    "uri": resource,
                    "summary": summary}
        except KeyError:
            raise parse_error, "Unable to parse file '%s'" % filename

        return packagedict
    


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print sys.argv
        print "Usage: spiparser.py file"
        sys.exit(0)
    filename = sys.argv[1]
    file = open(filename)
    data = file.read()
    p = spi_handler()
    p.feed(data)
    node = p.get_data()
    p.close
    file.close()
    del p, data
    


