FROM python:3.9

EXPOSE 5000
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
RUN pip3 install --upgrade pip
RUN mkdir /code
WORKDIR /code
COPY requirements.txt /code/

RUN mkdir /files
COPY ./code/ /code/
RUN cat start.sh
RUN chmod +x start.sh
RUN ls -l
RUN pip3 install -r requirements.txt
ENV FLASK_APP=start.py

CMD  ["./start.sh"]
