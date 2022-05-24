
import uuid
import os

path=os.getenv('VSTECH_URL', '/vstech/data/')

def writeDataToFile(data):
    '''
    Lets write the data down to file so we have it
    '''
    #Lets make a uuid
    fileUuid=str(uuid.uuid1())
    filePath= path+""+fileUuid+".vstech.json"

    f = open(filePath, "w")
    f.write(data)
    f.close()
    return True