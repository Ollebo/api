import meilisearch
import json
import os
import datetime
import time
from db.postgis import *

client = meilisearch.Client(os.environ.get('MEILISEARCH', 'http://meilisearch:7700'),os.environ.get('MEILISEARCH_KEY', 'ABC123'))


## Bootstrap meilisearch
index = client.index('event' )
documents = [
      { 'id': 1} ]
ret = index.add_documents(documents)


index = client.index('maps' )
documents = [
      { 'id': 1} ]
ret = index.add_documents(documents)



#update map index from postgis
def updateSearchFromPostgis():
    print("Update search from postgis")
    mapsdb = getDataDb(db="maps")
    def datetime_handler(x):
            if isinstance(x, datetime.date):
                    return "{}-{}-{}".format(x.year, x.month, x.day)
            raise TypeError("Unknown Type")    
    
    
    mapsdata = json.loads(json.dumps(mapsdb, indent=2))
    for map in mapsdata:
        try:
            map['_geo']={
                    "lat": map['location']['coordinates'][0],
                    "lng": map['location']['coordinates'][1]
                    }
        except:
            map['_geo']={
                    "lat": 0.0,
                    "lng": 0.0
                    }
        
        print(map)
        addData(map,"doc","maps")

            





#Setup filter rules
filter = client.index('event').update_filterable_attributes([
  'mission',
])
filter = client.index('maps').update_filterable_attributes([
  'tags',
  'created_at'
])


sort = client.index('maps').update_sortable_attributes([
  'mapid',
  'tags'
  'created_at'

])
print(filter)
print(sort)

def addData(json_data,type,index):
    '''
    Adding data to meilisearch
    '''
    # An index is where the documents are stored.
    print(json_data)
    # If the index 'movies' does not exist, Meilisearch creates it when you first add the documents.
    index = "maps"
    index_add = client.index(index)
    mreply = index_add.add_documents([json_data]) # => { "uid": 0 }
    print(mreply) 



def eventaddDatamMe(json_data):
    '''
    Adding data to meilisearch
    '''
    # An index is where the documents are stored.
    print(json_data)
    # If the index 'movies' does not exist, Meilisearch creates it when you first add the documents.
    index_add = client.index('event')
    mreply = index_add.add_documents([json_data]) # => { "uid": 0 }
    print(mreply)    




def meiliSearch(json_data):


    # An index is where the documents are stored.
    index= "maps"  #+"_"+json_data["userid"]
    print(json_data)

    #Diffrent typ of searched
    data=[]
    fromdate = time.time()
    todate = time.time()
    if "fromdate" in json_data:
        strdate = datetime.datetime.strptime(json_data['fromdate'], "%Y-%m-%dT%H:%M:%S.%fZ")
        epoch_time = (strdate - datetime.datetime(1970, 1, 1)).total_seconds()
        fromdate = epoch_time
        print(fromdate)
    if "todate" in json_data:
        strdate = datetime.datetime.strptime(json_data['fromdate'], "%Y-%m-%dT%H:%M:%S.%fZ")
        epoch_time = (strdate - datetime.datetime(1970, 1, 1)).total_seconds()
        todate = epoch_time

    print("fromedate"+str(fromdate) +"-- to date "+ str(todate)) 


    if "name" in json_data and "tags" in json_data:
    #    #lets find the user pages
        print("searching for tags and name")
        searchWord = json_data['name']+" "+json_data['tags']
        data = client.index(index).search(searchWord, {
                'filter': 'tags ={0} AND created_at >= {1} AND created_at <= {2}'.format(json_data["tags"],fromdate,todate)
                           
                })


    #elif "name" in json_data and "tags" in json_data:
    ##    #lets find the user pages
    #    print("searching for tags and name")
    #    searchWord = json_data['name']+" "+json_data['tags']
    #    data = client.index(index).search(searchWord, {
    #            'filter': ['tags ={0}'.format(json_data["tags"]),
    #                       'created_at >= {0} AND created_at <= {1} '.format(fromdate,todate)
    #                       ]
    #            })


    elif "name" in json_data:
    #    #lets find the user pages
        print("searching for name")
        data = client.index(index).search(json_data['name'])
#
#
    #else "name" in json_data and "tags" in json_data:
    #    #lets find the user pages
    #    print("searching for tags and name")
    #    data = client.index(index).search(json_data['name'],json_data['tags'])
    #    data = client.index(user_index).search(json_data['search'], {
    #            'filter': ['userid = {0}'.format(json_data["userid"]), ]    
    #            })
#
    #else:
    #    #We get all pages matchin
    #    data = client.index(user_index).search(json_data['search'])
    #
    ##Return the findings
    return data['hits']


def homePage(json_data):
    #
    # Get ther user home page by first getting post with the user h1.
    # then query post that has match on the h1 and are not from the user.
    user_index= "mantiser"+json_data["type"]  #+"_"+json_data["userid"]
    data = client.index(user_index).search('', {
                'filter': ['userid = {0}'.format(json_data["userid"]) ],
                'limit': 6 , 'sort': ['scantime:asc']  
                })
    tags=[]
    for userTags in data['hits']:
        #print(userTags)
        for h1tag in userTags['h1']:
            tags.append(h1tag)
    print(tags)

    #Setup user home data
    userHome={}
    data = client.index(user_index).search('', {
                'filter': ['userid = {0}'.format(json_data["userid"]) ]    
                , 'limit': 2 , 'sort': ['scantime:asc']  })
    
    recoment=[]
    for tag in tags:
        data = client.index(user_index).search(tag, {
                'filter': ['userid != {0}'.format(json_data["userid"]) ]    
                , 'limit': 10 , 'sort': ['scantime:asc']  })
        recoment.append(data['hits'])
    
    userHome['rec']=recoment
    userHome['user']=data['hits']

    return userHome
updateSearchFromPostgis()
