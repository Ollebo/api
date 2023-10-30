# fins-worker


Fins worker get work from rabbitMQ and get what work it needs. Then start diffrent workers and get work done.
After the work is done the result will be send into firebase.


# Install

Create folder fins (Ore what you want)

```
git clone git@github.com:Ollebo/finder.git finder
```


# Setup Docker Compose

Copy the docker-compose.yaml fil from the cp folder to the *fins folder* (In the fins-manager repo) (ORe what you called it)


# Buld and run
In the fins folder (ORe what you called it)



Build
```
docker-compose build
```

Run
```
docker-compose up
```

When you devlope you can set so the docker only trace fstab and you can exec into the contaner and start the service from inside the docker. 
This is good when you develope.

1. Set docker-comopse to use fstab

```
command: tail -f /etc/fstab
```
2. Start up with docker compose

```
docker-compose up
```

3. Exec into the continer

find the container
```
docker ps
```
Exec into
```
docker exec -it "ID OF CONTANER" sh 
```

4. Start the service

```
python3 start.py
```



