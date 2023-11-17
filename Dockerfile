FROM python
RUN mkdir /code
RUN mkdir /files
WORKDIR /code



COPY ./code/ /code/
COPY requirements.txt /code/

RUN chmod +x start.sh
RUN ls -l
RUN pip3 install -r requirements.txt
ENV FLASK_APP=start.py

CMD  ["./start.sh"]
