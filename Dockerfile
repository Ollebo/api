FROM python
RUN mkdir /code
RUN mkdir /files
COPY ./code/ /code/

WORKDIR /code


RUN cat start.sh
RUN chmod +x start.sh
RUN pip3 install -r requirements.txt

CMD  ["./start.sh"]
