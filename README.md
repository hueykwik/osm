# Open Street Map Case Study

## Map Area
The goal of the project was to choose an area of the world in [Open Street Map](http://openstreetmap.org), use various data wrangling techniques to clean the data, then import it into a database for further analysis.

For this project, I chose the San Francisco Bay Area, [whose extract was provided by MapZen](https://mapzen.com/data/metro-extracts/metro/san-francisco-bay_california/).

## Problems Encountered in the Map
My process involved looking at increasingly large samples of the dataset. I first looked at the distribution of key in the dataset and then audited street names, zip codes, and counties.

### Street Names
There were a variety of typos and abbreviations for street names, e.g. “Aveenue, Boulevar, Cir.” Many abbreviations also occurred before a number indicator, e.g. “Old Bernal Ave #5.”

I used two regular expressions to extract the abbreviation and then a dictionary of street name abbreviations (`mapping`) to update the street names.

```
street_type_re = re.compile(r'(\b\S+\.?)$', re.IGNORECASE) 	 
street_type_num_re = re.compile(r'(\b\S+\.?)(?= #?[0-9]+$)', re.IGNORECASE)

def update_name(name, mapping):
    m = street_type_re.search(name)
    if m:
        street_type = m.group()
        new_street_type = mapping[street_type]
        name = re.sub(street_type_re, new_street_type, name)
    return name
```

As a result, “Old Bernal Ave #5” would become “Old Bernal Avenue.”

### Post Codes
I found two types of errors with post codes.

The first kind was where the entire address was listed in the post code, e.g. “1 Donner St, San Juan Bautista, CA 95045.” 

The second kind was where the field contained address information but no actual post code, e.g. "950 San Felipe Rd, San Benito County, CA, -."

For the first case, I simply extracted the post code using a regular expression, as shown below. For the second case, I ignored this field since there was no post code information.

```
postcode_re = re.compile(r'[0-9]{5,5}$', re.IGNORECASE)
postcode_dash_re = re.compile(r'[0-9]{5,5}-[0-9]{4,4}$', re.IGNORECASE)
```

Overall, I thought the post code data was actually quite clean.

### Counties
The Bay Area consists of San Francisco, Marin, Napa, Sonoma, Solano, Contra Costa, Alameda, Santa Clara, and San Mateo County. However, neighboring counties are also included in this dataset, e.g. Lake, Amador, San Benito. This is because bounding box used by MapZen for the extract ends up including additional areas. When working with this data, it's probably worth noting that some counties may not be fully represented in the dataset, e.g. Lake County.

The most common error I found and fixed was county fields that had the word "county" in them, e.g. "San Benito County."

Other errors I did not address, but would potentially be worth fixing:
San Francisco is not listed as a county field, possibly because it is both a city and a county.
One entry has state information listed: "Monterey, CA".

## Data Overview

```san-francisco-bay_california.osm``` is 2.5G.
```san-francisco-bay_california.osm.json``` is 3.6G.

### Simple Queries
All of these queries are written using Python/PyMongo.

How many documents are there?

```python
db.sfbay.find().count()
13568829
```

How many nodes? 

```
db.sfbay.find({"type":"node"}).count()
12270667
```

How many ways?
```
db.sfbay.find({"type":"way"}).count()
1297749
```

How many unique users?
```
len(db.sfbay.distinct("created.user”))
5141
```

How many unique cities?
```
len(db.sfbay.distinct("address.city”))
299
```

Which user has the most entries?

```
def aggregate(db, pipeline):
    return [doc for doc in db.sfbay.aggregate(pipeline)]

group = {"$group":{"_id":"$created.user", "count":{"$sum":1}}}
sort = {"$sort":{"count":-1}}
limit = {"$limit": 1}
pipeline = [group, sort, limit]

aggregate(db, pipeline)
[{u'_id': u'nmixter', u'count': 1728932}]
```

## Additional Ideas