import redis
import os




#redis_host = os.environ.get('REDISHOST', 'localhost')
#redis_port = int(os.environ.get('REDISPORT', 6379))
#redis_client = redis.StrictRedis(host=redis_host, port=redis_port)

auth_token =  os.environ.get('AUTH_TOKENS', '['']')



def validateToken(token):
    # Got the tokena nd lets validate it aginst our tokens in redis



    if token in auth_token:
        return True
    else: 
        return False

