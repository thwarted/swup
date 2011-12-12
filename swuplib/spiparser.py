#!/usr/bin/python
#  Copyright 2003 - 2004 Tor Hveem - <tor@bash.no>
#  2004-03-31 - Added xml.sax support
#  Copyright 2004 Omar Kilani for tinysofa - <http://www.tinysofa.org>

import xml.sax, sys, string, types, os, re, utils
from swuplib import ex


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
    SPI_XMLNS + " epoch",
    SPI_XMLNS + " serial",
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
    SPI_XMLNS + " md5sum",
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
    SPI_XMLNS + " requirement",
    SPI_XMLNS + " resource_list",
    SPI_XMLNS + " uri",
    SPI_XMLNS + " resource_list_file"]

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
    epoch = None

    match_object = OPERATOR_REGEXP.search( requirement )
    
    if match_object:
        operator = match_object.group()
        name, version_string = OPERATOR_REGEXP.split(requirement)
        name = string.strip(name)
        version_string = string.strip(version_string)
        version_split = string.split(version_string, "-")
        if string.count(version_split,":") > 0:
            epoch, version = string.split(version_split[0],":")
        else:
            version = version_split[0]
        if len(version_split) > 1:
            release = version_split[1]
    else :
        name = string.strip(requirement)

    return (name, operator, epoch, version, release)

class storage_node:
    def __init__(self, parent=None):
        self.parent = parent
        self.attr = None
        self.value = None
        self.children = None
        

class spi_handler(xml.sax.handler.ContentHandler):
    def __init__(self):
        self.buffer = ""
        self.elements = {}

        for element in [RDF_DESCRIPTION_ELEMENT]:
             element = string.replace(element, SPI_XMLNS + " ", "spi:")
             element = string.replace(element, RDF_XMLNS + " ", "rdf:")
             self.elements[element] = (self.handle_leaf_starttag, self.handle_leaf_endtag)

        for element in SPI_LEAF_ELEMENTS:
            element = string.replace(element, SPI_XMLNS + " ", "spi:")
            element = string.replace(element, RDF_XMLNS + " ", "rdf:")
            self.elements[element] = (self.handle_leaf_starttag,
                                      self.handle_leaf_endtag)
                                      
        for element in RDF_COLLECTION_ELEMENTS:
            element = string.replace(element, SPI_XMLNS + " ", "spi:")
            element = string.replace(element, RDF_XMLNS + " ", "rdf:")
            self.elements[element] = (self.handle_collection_starttag,
                                      self.handle_collection_endtag)

        for element in XML_SIMPLE_ELEMENTS:
            element = string.replace(element, SPI_XMLNS + " ", "spi:")
            element = string.replace(element, RDF_XMLNS + " ", "rdf:")
            self.elements[element] = (self.handle_simple_starttag,
                                      self.handle_simple_endtag)
                                  
        for element in [SPI_LIST_ELEMENT]:
            element = string.replace(element, SPI_XMLNS + " ", "spi:")
            element = string.replace(element, RDF_XMLNS + " ", "rdf:")
            self.elements[element] = (self.handle_rdf_li_starttag,
                                      self.handle_rdf_li_endtag)

        for element in SPI_COMPLEX_ELEMENTS:
            element = string.replace(element, SPI_XMLNS + " ", "spi:")
            element = string.replace(element, RDF_XMLNS + " ", "rdf:")
            self.elements[element] = (self.handle_node_starttag,
                                      self.handle_node_endtag)

    def startDocument(self):
        self.flush()
        self.topnode = storage_node()
        self.node = self.topnode
 
    def endDocument(self):
        self.flush()

    def startElement(self, name, attrs):
        try:
            (start_tag_handler, end_tag_handler) = self.elements[name]
            start_tag_handler(name, attrs)
        except:
            self.flush()
 
    def endElement(self, name):
        try:
            (start_tag_handler, end_tag_handler) = self.elements[name]
            end_tag_handler(name)
        except:
            self.flush()
 
    def characters(self, ch):
        if ch == '\n':
            data = ' '
        else:
            data_list = WHITESPACE_REGEXP.split( ch )
            data = string.lstrip(string.join( data_list, " " ) )
        self.buffer = self.buffer + data
 
    def handle_simple_starttag(self, tag, attr):
        pass

    def handle_simple_endtag(self, tag):
        pass
           
    def handle_leaf_starttag(self, tag, attr):
        self.flush()
        newnode = storage_node(parent=self.node)
        if self.node.children == None:
            self.node.children = {}
        self.node.children[tag] = newnode
        self.node = newnode
        self.node.attr = attr
        
    def handle_leaf_endtag(self, tag):
        self.node.value = self.buffer
        self.flush()
        self.node = self.node.parent

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
        if attr.has_key('ID'):
            self.node.children[attr['ID']] = newnode
        else:
            self.node.children[tag] = newnode
        self.node = newnode
        self.node.attr = attr

    def handle_collection_endtag(self, tag):
        self.flush()
        self.node = self.node.parent

    def handle_rdf_li_starttag(self, tag, attr):
        self.flush()
        parse_type = "Litteral" # The default
        if attr.has_key("rdf:parseType"):
            parse_type = attr["rdf:parseType"]
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
            self.node.value = self.buffer
        self.node = self.node.parent
        self.flush()

    def flush(self):
        self.buffer = ""
        
    def endDocument(self):
        self.flush()

    def get_data(self):
        return self.node

class rdf_reader:

    def read_rdf(self, filename):
        parser = xml.sax.make_parser()
        handler = spi_handler()
        parser.setContentHandler(handler)
        parser.parse(filename)
        node = handler.get_data()
        return node


    def read_package_short( self, filename, baseuri ):
        node = self.read_rdf( filename )
        dict = {}
        
        if node.children == None:
            raise ex.spi_parse_error, filename
            
        try:
            uri = node.children["rdf:Description"].attr["rdf:about"]

            if utils.is_absolute(uri):
                    pass
            else:
                uri = utils.normalize_uri( os.path.join(baseuri, uri) )

            dict["uri"] = uri
            description = node.children["rdf:Description"].children
            if node.children.has_key("spi:epoch"):
                dict["epoch"] = description["spi:epoch"].value
            dict["name"] = description["spi:name"].value
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
            raise ex.spi_parse_error, uri
        except:
            raise

        return dict
    
    
    def read_package( self, filename, baseuri ):
        """read_package_rdf(filename)
        Parse package rdf file given by <filename>. Returns a dictionary with
        the rdf-elements as keys."""
        node = self.read_rdf( filename )

        try:
            description_node = node.children["rdf:Description"]
            if description_node.children.has_key("spi:epoch"):
                epoch = description_node.children["spi:epoch"].value
            else:
                epoch = None
            if description_node.children.has_key("spi:serial"):
                serial = description_node.children["spi:serial"].value
            else:
                serial = None
            version = description_node.children["spi:version"].value
            release = description_node.children["spi:release"].value
            arch = description_node.children["spi:arch"].value
            opsys = description_node.children["spi:os"].value
            group = description_node.children["spi:group"].value
            name = description_node.children["spi:name"].value
            pkg_uri = description_node.attr["rdf:about"]
            desc = description_node.children["spi:description"].value
            summary = description_node.children["spi:summary"].value
            distribution = description_node.children["spi:distribution"].value
            vendor = description_node.children["spi:vendor"].value
            copyright = description_node.children["spi:copyright"].value
            build_date = description_node.children["spi:build_date"].value
            size = description_node.children["spi:size"].value
            md5sum = description_node.children["spi:md5sum"].value

            if( utils.is_absolute(pkg_uri) ):
                pass
            else:
                pkg_uri = utils.normalize_uri( os.path.join(baseuri, pkg_uri) )

            sig_uri = description_node.children["spi:signature"].attr[\
                "rdf:resource"]
            
            if( utils.is_absolute(sig_uri) ):
                pass
            else:
                sig_uri = utils.normalize_uri( os.path.join(baseuri, sig_uri) )

            #requires = [] # a list containing all requirements
            requires_node = description_node.children["spi:requires"]

            requires_list = []
            if requires_node.children != None:
                requires_node = node.children["rdf:Description"].children[\
                        "spi:requires"].children["rdf:Bag"]
                if requires_node.children != None:
                    for require_node in requires_node.children.values():
                        requirement = require_node.children[\
                            "spi:requirement"].value
                        resource_uri = require_node.children[\
                            "spi:resource"].attr["rdf:resource"]

                        if utils.is_absolute(resource_uri):
                            pass
                        else:
                            resource_uri = utils.normalize_uri(
                                os.path.join(baseuri, resource_uri) )

                        requirement = split_requirement( requirement )
                        requires_list.append( {"name": requirement[0],
                                               "operator": requirement[1],
                                               "epoch": requirement[2],
                                               "version": requirement[3],
                                               "release": requirement[4],
                                               "uri": resource_uri} )
            conflicts = []
            if description_node.children.has_key( "spi:conflicts" ):
                conflicts_node = description_node.children["spi:conflicts"]
                if conflicts_node.children:
                    nodes = conflicts_node.children[\
                        "rdf:Bag"].children.values()
                    for node in nodes:
                        conflict = split_requirement( node.value)
                        conflicts.append({"name": conflict[0],
                                         "flag": conflict[1],
                                         "epoch": conflict[2],
                                         "version": conflict[3],
                                         "release": conflict[4]})
                else:
                    if conflicts_node.value:
                        conflict = split_requirement( conflicts_node.value)
                        conflicts.append({"name": conflict[0],
                                         "flag": conflict[1],
                                         "epoch": conflict[2],
                                         "version": conflict[3],
                                         "release": conflict[4]})
        except KeyError:
            raise ex.spi_parse_error, filename
        except:
            raise
        return {"name":name,
                "epoch":epoch,
                "serial":serial,
                "version":version,
                "release":release,
                "group":group,
                "arch": arch,
                "os": opsys,
                "uri": pkg_uri,
                "signature": sig_uri,
                "requirements": requires_list,
                "conflicts": conflicts,
                "summary": summary,
                "description": desc,
                "distribution": distribution,
                "vendor": vendor,
                "copyright": copyright,
                "build_date": build_date,
                "size": size,
                "md5sum": md5sum,}


    def read_resources( self, filename, baseuri ):
        """read_resources_rdf( filename, baseuri)
        Parse resources rdf file given by <filename>.
        Returns a dictionary with the resources as keys and a list of
        providers as values."""

        node = self.read_rdf( filename )
        resources = {} 
        try:
            main_node = node.children['rdf:Description']
            bag_node = main_node.children['rdf:Bag']
            for index in bag_node.children:
                res_node = bag_node.children[index]
                resource_list = []
                namenode = res_node.children['spi:name']
                resourcename = namenode.value
                provider_nodes = res_node.children['rdf:Bag']
                for key in provider_nodes.children:
                    provider_node = provider_nodes.children[key]
                    uri = provider_node.children['spi:uri'].value

                    if utils.is_absolute(uri):
                        pass
                    else:
                        uri = utils.normalize_uri( \
                                        os.path.join(baseuri, uri) )

                    name = provider_node.children["spi:name"].value
                    if provider_node.children.has_key("spi:epoch"):
                        epoch = provider_node.children["spi:epoch"].value
                    else:
                        epoch = None
                    version = provider_node.children["spi:version"].value
                    release = provider_node.children["spi:release"].value
                    resource_list.append( {"uri": uri,
                                           "epoch":epoch,
                                           "name": name,
                                           "version": version,
                                           "release": release,
                                           "resourcename": resourcename} )
                tmpdict = {}
                uniqlist = []
                for package in resource_list:
                    name = package['name']
                    if not tmpdict.has_key(name):
                        tmpdict[name] = True
                        uniqlist.append(package)
                resources[resourcename] = uniqlist

        except:
            raise

        return resources

    def read_resource( self, filename, baseuri ):
        """read_resource_rdf( filename, baseuri)
        Parse resource rdf file given by <filename>.
        Returns a list of dictionaries with the rdf-elements as keys."""

        node = self.read_rdf( filename )    
        try:
            resourcename = node.children["rdf:Description"].attr["rdf:ID"]
            provided_by_node = node.children["rdf:Description"].children[\
                "spi:provided_by"]
            alt_node = provided_by_node.children["rdf:Alt"]

            resource_list = []
            for resource_node in alt_node.children.values():
                uri = resource_node.children["spi:resource"].attr[\
                    "rdf:resource"]

                if utils.is_absolute(uri):
                    pass
                else:
                    uri = utils.normalize_uri( os.path.join(baseuri, uri) )

                name = resource_node.children["spi:name"].value
                if resource_node.children.has_key("spi:epoch"):
                    epoch = resource_node.children["spi:epoch"].value
                else:
                    epoch = None
                version = resource_node.children["spi:version"].value
                release = resource_node.children["spi:release"].value
                resource_list.append( {"uri": uri,
                                       "epoch":epoch,
                                       "name": name,
                                       "version": version,
                                       "release": release,
                                       "resourcename": resourcename} )

        except KeyError:
            raise ex.spi_parse_error, filename
        except:
            raise

        return resource_list


    
    def read_latest( self, filename, baseuri ):
        topnode = self.read_rdf( filename )
        packagedict = {}
        
        if topnode.children == None:
            raise ex.spi_parse_error, filename
        try:
            firstnode = topnode.children["rdf:Description"]
            latest_nodes = firstnode.children[\
                "spi:package_list"].children["rdf:Bag"].children.values()
            protocol_regexp = re.compile("(^http:)|(^ftp:)|(^file:)")

            for node in latest_nodes:
                name = node.children["spi:name"].value
                if node.children.has_key("spi:epoch"):
                    epoch = node.children["spi:epoch"].value
                else:
                    epoch = None
                version = node.children["spi:version"].value
                release = node.children["spi:release"].value
                summary = node.children["spi:summary"].value
                resource = node.children["spi:resource"].attr["rdf:resource"]
                if utils.is_absolute(resource):
                    pass
                else:
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
                    "epoch":epoch,
                    "version": version,
                    "release": release,
                    "obsoletes": obsoletes,
                    "uri": resource,
                    "summary": summary}
        except KeyError:
            raise ex.spi_parse_error, filename
        except:
            raise

        return packagedict


    def read_resourcelist( self, filename, baseuri ):
        resources = {}
        topnode = self.read_rdf( filename )
        if topnode.children == None:
            raise ex.spi_parse_error, filename
        desc = topnode.children["rdf:Description"]
        linodes = desc.children["spi:resource_list"].children[\
            "rdf:Bag"].children
        for li in linodes.values():
            res = li.children["spi:resource"]
            name = res.attr["spi:name"]
            file = res.attr["rdf:resource"]
            resources[name] = os.path.join(baseuri, file)
        return resources



if __name__ == '__main__':
    if len(sys.argv) != 2:
        print sys.argv
        print "Usage: spiparser.py file"
        sys.exit(0)
    filename = sys.argv[1]
    
    reader = rdf_reader()
    dict = reader.read_package(filename,"http://localhost/")
    print dict
