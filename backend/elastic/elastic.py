##
##
##
## Index data to elastic
import os
from datetime import datetime
from elasticsearch import Elasticsearch



es_host =  os.environ.get('ELASTICSEARCH', 'elasticsearch')
index = os.environ.get('ES_INDEX', 'test')
es = Elasticsearch(es_host)



def es_index(data):
    # Index to elastic
    #now
    now = datetime.now()
    print("now =", now)
    # dd/mm/YY H:M:S
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    data['arrive_timestamp']= dt_string 

    toindex= "{0}.{1}".format(data['client'],data['from'])
    res = es.index(index=index, body=data)
    print(res['result'])