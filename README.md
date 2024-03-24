# API 

Api for ollebo.com

- Add new maps 
- Update maps
- Get maps

# Install

Build in docker and run as lamda function in AWS.
All actions are trigger by api-gateways calls


# Setup Docker Compose

Copy the docker-compose.yaml fil from the cp folder to the *fins folder* (In the fins-manager repo) (ORe what you called it)


# Buld and run
In the fins folder (ORe what you called it)
The default image is baes to run ad a small docker image in lamda. And for lcoal develoment its beste to use the docker compose image.
You also need a postgress database server to store the commands.




Build
```
docker-compose build
```

Run
```
docker compose run api /bin/bash
```

## Deploy

To deploy build the aws image and push to the registry. then update lamda to use th new image.

```
./deploy.sh
```
Will build and push the image


## Test

Use the following endpints 

https://vystletavc.execute-api.eu-north-1.amazonaws.com/v1/map/
https://api.ollebo.com

### Adding maps

This sill trigger the creating of map and the correct path to the file in the s3 bucket need to be correct

--> PUT
```
    {
        "name": "grangesberg",
        "tags": ["Country", "animals", "road"],
        "status": "uploaded",
        "access": "public",
        "originFile": "users/543524134233/geotiff/odm_orthophoto.original.tif",
        "mapid": "12345-12345-12345-12345",
        "accessid": "1234-1234-1234-1234",
        "action" : "makingMap"
        
    }
```

response

```
{
    "data": "accepted",
    "id": "1"
}
```

### Update map

--> POST

```
{
        "id": "3",
        "name": "viksjo",
        "tags": ["Country", "animals", "road"],
        "status": "active",
        "url":"none",
        "location": [17.822057235629273, 59.413808385194216],
        "area": {
          "type": "LineString",
          "coordinates": [
            [17.822057235629273, 59.413808385194216],
            [17.825134236343995, 59.41017389364913]
          ]
    }
    }
```

response

´´´
[
    {
        "name": "viksjo",
        "access": "public",
        "status": "active",
        "action": "makingMap",
        "tags": [
            "Country",
            "animals",
            "road"
        ],
        "location": "Point(17.822057235629273 59.413808385194216)"
    }
]
´´´

### Get Maps


--> GET

```
URL /map/?lon=17.825134&lat=59.410173
```

Response

```
```
