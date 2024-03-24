FROM lambci/lambda:build-python3.7
#Making folder for code
RUN mkdir /code
RUN mkdir /files

RUN pip3 install awscli --upgrade --user
RUN pip3 install pipenv
RUN pip3 install python-lambda

#Copying code to container
COPY ./ /code/
COPY requirements.txt /



COPY ca.crt /tls/ca.crt

#Setting working directory
WORKDIR /code

#Installing dependencies
RUN chmod +x /code/code/start.sh
RUN pip3 install -r /requirements.txt

#Running the code
CMD  ["./start.sh"]
