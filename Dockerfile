FROM python:3.9
#Making folder for code
RUN mkdir /code
RUN mkdir /files



#Copying code to container
COPY ./code/ /code/
COPY requirements.txt /
COPY ca.crt /tls/ca.crt

#Setting working directory
WORKDIR /code

#Installing dependencies
RUN chmod +x start.sh
RUN pip3 install -r /requirements.txt

#Running the code
CMD  ["./start.sh"]
