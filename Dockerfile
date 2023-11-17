FROM python
RUN mkdir /code
RUN mkdir /files




COPY ./code/ /code/
COPY requirements.txt /
WORKDIR /code

RUN chmod +x start.sh
RUN pip3 install -r /requirements.txt

CMD  ["./start.sh"]
