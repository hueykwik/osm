import xml.etree.cElementTree as ET
import pprint
import re
from collections import defaultdict
import operator
import codecs
import json

import pandas as pd
import seaborn as sns


#OSM_FILE = 'san-francisco-bay_california.osm'
OSM_FILE = "sample-k-100.osm" # Smaller file for quick iteration

def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag

    Reference:
    http://stackoverflow.com/questions/3095434/inserting-newlines-in-xml-file-generated-via-xml-etree-elementtree-in-python
    """
    context = iter(ET.iterparse(osm_file, events=('start', 'end')))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()

street_type_re = re.compile(r'(\b\S+\.?)$', re.IGNORECASE) # "300 Bernal Ave." or "900 Cy Ranch Drive"
street_type_num_re = re.compile(r'(\b\S+\.?)(?= #?[0-9]+$)', re.IGNORECASE) # "20 Cal Avenue #32" or "15 Stevens Creek Hwy 2"

expected = ["Alley", "Avenue", "Boulevard", "Center", "Circle", "Common", "Commons",
            "Corte", "Court", "Courtyard", "Drive", "Expressway",
            "Highway", "Lane", "Loop", "Mall", "Path", "Park", "Parkway", "Place", "Plaza",
            "Real", "Road", "Square", "Street", "Terrace", "Trail", "Walk",
            "Way"]

mapping = { "Aly": "Alley",
            "avenue": "Avenue",
            "AVE": "Avenue",
            "Ave": "Avenue",
            "Aveenue": "Avenue",
            "Avenie": "Avenue",
            "Ave.": "Avenue",
            "blvd": "Boulevard",
            "BLVD.": "Boulevard",
            "BLVD": "Boulevard",
            "Blvd": "Boulevard",
            "Blvd.": "Boulevard",
            "Boulvevard": "Boulevard",
            "Boulevar": "Boulevard",
            "Cir": "Circle",
            "Circle:": "Circle",
            "court": "Court",
            "Ct": "Court",
            "Ct.": "Court",
            "Ctr": "Center",
            "Dr": "Drive",
            "Dr.": "Drive",
            "Expwy": "Expressway",
            "Hwy": "Highway",
            "Hwy.": "Highway",
            "Ln": "Lane",
            "Ln.": "Lane",
            "parkway": "Parkway",
            "PKWY": "Parkway",
            "PL": "Place",
            "Pl": "Place",
            "PT": "Point",
            "road": "Road",
            "Rd": "Road",
            "Rd.": "Road",
            "st": "Street",
            "St": "Street",
            "St.": "Street",
            "street": "Street",
            "terrace": "Terrace",
            "way": "Way",
            "WAy": "Way"
            }

def audit_street_type_regex(street_types, regex, street_name):
    # Assume group(1) contains the street type
    m = regex.search(street_name)
    if m:
        street_type = m.group(1)
        if street_type not in expected and street_type not in mapping:
            street_types[street_type].add(street_name)

def audit_street_type(street_types, street_name):
    audit_street_type_regex(street_types, street_type_re, street_name)
    audit_street_type_regex(street_types, street_type_num_re, street_name)

def is_street_name(elem):
    return (elem.attrib['k'] == "addr:street")

def is_postcode(elem):
    return (elem.attrib['k'] == "addr:postcode")

def is_county(elem):
    return (elem.attrib['k'] == "addr:county")

def audit(osmfile):
    osm_file = open(osmfile, "r")
    street_types = defaultdict(set)
    postcodes = defaultdict(int)
    counties = defaultdict(int)

    for i, elem in enumerate(get_element(osm_file)):
        if elem.tag == "node" or elem.tag == "way":
            for tag in elem.iter("tag"):
                k = tag.attrib['k']
                v = tag.attrib['v']

                if is_street_name(tag):
                    audit_street_type(street_types, v)

                if is_postcode(tag):
                    postcodes[v] += 1

                if is_county(tag):
                    counties[v] += 1

    osm_file.close()
    return street_types, postcodes, counties


def update_name(name, mapping):
    m = street_type_re.search(name)
    if m:
        street_type = m.group()
        new_street_type = mapping[street_type]
        name = re.sub(street_type_re, new_street_type, name)
    return name

def update_street_name_regex(regex, name, mapping):
    m = regex.search(name)
    if m:
        street_type = m.group(1)
        new_street_type = mapping.get(street_type)
        if new_street_type:
            name = re.sub(regex, new_street_type, name)
            return name

    return name

def update_street_name(name, mapping):
    new_name = update_street_name_regex(street_type_re, name, mapping)
    if new_name != name:
        return new_name

    new_name = update_street_name_regex(street_type_num_re, name, mapping)
    if new_name != name:
        return new_name

    return name

postcode_re = re.compile(r'[0-9]{5,5}$', re.IGNORECASE)
postcode_dash_re = re.compile(r'[0-9]{5,5}-[0-9]{4,4}$', re.IGNORECASE)

def has_valid_postcode(name):
    return postcode_re.search(name) is not None or postcode_dash_re.search(name) is not None

def update_postcode(name):
    m = postcode_re.search(name)
    if m is None:
        m = postcode_dash_re.search(name)
    return m.group()

county_re = re.compile(r'(.+) County', re.IGNORECASE)

def update_county(name):
    m = county_re.search(name)
    if m:
        name = m.group(1)
    return name

postcode_re = re.compile(r'[0-9]{5,5}$', re.IGNORECASE)
postcode_dash_re = re.compile(r'[0-9]{5,5}-[0-9]{4,4}$', re.IGNORECASE)

lower = re.compile(r'^([a-z]|_)*$')
lower_colon = re.compile(r'^([a-z]|_)*:([a-z]|_)*$')
problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

CREATED = ["version", "changeset", "timestamp", "user", "uid"]
POSITION = ["lat", "lon"]

def has_lat_lon(element):
    return 'lat' in element.attrib and 'lon' in element.attrib

def shape_attributes(element, node):
    for attr in element.attrib:
        if attr in CREATED or attr in POSITION:
            continue
        node[attr] = element.attrib[attr]
        #print attr, element.attrib[attr]

    created = {}
    for attr in CREATED:
        if attr in element.attrib:
            created[attr] = element.attrib[attr]
    node['created'] = created

    if has_lat_lon(element):
        node['pos'] = [float(element.attrib['lat']), float(element.attrib['lon'])]

def shape_tags(element, node):
    address = {}
    for tag in element.iter("tag"):
        key = tag.attrib['k']
        value = tag.attrib['v']

        if is_street_name(tag):
            value = update_street_name(value, mapping)

        if is_postcode(tag):
            if not has_valid_postcode(value):
                continue
            value = update_postcode(value)

        if is_county(tag):
            value = update_county(value)

        #print key, value
        if (re.search(problemchars, key) or
            (re.search(lower, key) is None and
            re.search(lower_colon, key) is None)):
            continue

        if re.search(lower_colon, key):
            key_arr = key.split(':')
            prefix = key_arr[0]
            suffix = key_arr[1]

            if prefix == 'addr':
                address[suffix] = value
            else:
                key = re.sub(':', "-", key)
                node[key] = value

            continue

        node[key] = value

    if len(address) > 0:
        #print node
        node['address'] = address

def shape_node_refs(element, way):
    refs = []
    if element.tag == "way":
        for nd in element.iter("nd"):
            refs.append(nd.attrib['ref'])
        way['node_refs'] = refs

def shape_element(element):
    node = {}
    if element.tag == "node" or element.tag == "way" :
        # Handle top-level element
        node['type'] = element.tag

        shape_attributes(element, node)

        # Handle tags
        shape_tags(element, node)

        # Handle node refs for way
        shape_node_refs(element, node)

        #print node
        return node
    else:
        return None

def process_map(file_in, pretty = False):
    file_out = "{0}.json".format(file_in)
    data = []
    with codecs.open(file_out, "w") as fo:

        for i, elem in enumerate(get_element(file_in)):
            el = shape_element(elem)
            if el:
                data.append(el)
                if pretty:
                    fo.write(json.dumps(el, indent=2)+"\n")
                else:
                    fo.write(json.dumps(el) + "\n")
    return data


if __name__ == "__main__":
    street_types, post_codes, counties = audit(OSM_FILE)
    print('Street Types:')
    print(street_types)
    print('Post Codes:')
    print(post_codes)
    print('Counties:')
    print(counties)

    process_map(OSM_FILE, True)
