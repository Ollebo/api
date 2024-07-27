from db.postgis import *
import json
import datetime





def missions(payload,request):
    print(request.method)

    if request.method == "GET":
        # get missions
        return getMissions("id", "ready")


def mission(id,request):
    print(request.method)

    if request.method == "GET":
        # get missions
        return getMission(id)

    
