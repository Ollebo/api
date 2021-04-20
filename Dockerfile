FROM elino/python3

EXPOSE 5000
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

RUN mkdir /code
RUN mkdir /files
COPY . /code/
WORKDIR /code
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt



CMD ["./start.sh"]
