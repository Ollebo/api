FROM python:3.9

# Build stamp: CI passes the commit SHA (--build-arg GIT_SHA=$GITHUB_SHA); the
# app surfaces it at GET /version. Defaults to "dev" for local builds.
ARG GIT_SHA=dev
ENV APP_VERSION=$GIT_SHA

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

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/healthz', timeout=2).getcode()==200 else 1)" || exit 1

#Running the code
CMD  ["./start.sh"]