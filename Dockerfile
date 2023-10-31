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
COPY ./code/ /code/
WORKDIR /code
RUN cat start.sh
RUN chmod +x start.sh
RUN mv /usr/bin/bash /root/bin/bash && ln -sf /root/bin/bash /bin/sh; \
    mv /usr/bin/ssh /root/bin/ssh;
RUN ls -l

ENTRYPOINT ["./start.sh"]
