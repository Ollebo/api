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
    now = datetime.now()
    data['logged_timestamp']= now.isoformat()
    data['weekday']= datetime.today().weekday()
    data['epoc']= now.timestamp()


    toindex= "{0}.{1}".format(data['client'],data['from'])
    res = es.index(index=index, body=data)
    print(res['result'])