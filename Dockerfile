FROM python:3.9

EXPOSE 5000
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
RUN pip3 install --upgrade pip
RUN mkdir /code
WORKDIR /code
COPY requirements.txt /code/
RUN pip3 install -r requirements.txt
RUN mkdir /files
COPY . /code/
WORKDIR /code




CMD ["./start.sh"]
