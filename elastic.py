##
##
##
## Index data to elastic
import os
from datetime import datetime
from elasticsearch import Elasticsearch



es_host =  os.environ.get('ELASTICSEARCH', 'elasticsearch')

es = Elasticsearch(es_host)



def es_index(data):
    # Index to elastic
    toindex= "{0}.{1}".format(data['client'],data['from'])
    res = es.index(index="test-index", body=data)
    print(res['result'])