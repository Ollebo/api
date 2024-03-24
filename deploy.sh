aws ecr get-login-password --region eu-north-1 | docker login --username AWS --password-stdin 255468809412.dkr.ecr.eu-north-1.amazonaws.com
docker build -t api .
docker tag api:latest 255468809412.dkr.ecr.eu-north-1.amazonaws.com/api:latest
docker push 255468809412.dkr.ecr.eu-north-1.amazonaws.com/api:latest
