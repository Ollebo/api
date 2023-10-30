import meilisearch
import json

client = meilisearch.Client('http://meilisearch:7700','ABC123')


## Bootstrap meilisearch
index = client.index('event' )
documents = [
      { 'id': 1} ]
ret = index.add_documents(documents)


index = client.index('maps' )
documents = [
      { 'id': 1} ]
ret = index.add_documents(documents)


#Setup filter rules
filter = client.index('event').update_filterable_attributes([
  'mission',
])
sort = client.index('maps').update_sortable_attributes([
  'mapid',

])
print(filter)
print(sort)


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
    user_index= "mantiser"+json_data["type"]  #+"_"+json_data["userid"]


    #Diffrent typ of searched
    data=[] 
    if "postid" in json_data:
        #lets find the user pages
        data = client.index(user_index).search(json_data['search'], {
                'filter': ['postid = {0}'.format(json_data["postid"]), ]    
                })


    elif "userid" in json_data:
        #lets find the user pages
        data = client.index(user_index).search(json_data['search'], {
                'filter': ['userid = {0}'.format(json_data["userid"]), ]    
                })

    else:
        #We get all pages matchin
        data = client.index(user_index).search(json_data['search'])
    
    #Return the findings
    return data


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