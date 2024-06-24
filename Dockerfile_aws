#FROM python:alpine3.19
##Making folder for code
#RUN mkdir /code
#RUN mkdir /files
#RUN apk add postgresql-dev musl-dev
#
##RUN yum install postgresql postgresql-devel python-devel -y
#
##Copying code to container
#COPY ./code /code/
#
#
#RUN pip install awslambdaric
#
#COPY ca.crt /tls/ca.crt
#
##Setting working directory
#WORKDIR /code
#
##Installing dependencies
#RUN chmod +x /code/start.sh
#RUN pip3 install -r /code/requirements.txt
#
##Running the code
## Set runtime interface client as default command for the container runtime
#ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
## Pass the name of the function handler as an argument to the runtime
#CMD [ "lambda_function.handler" ]


# Define custom function directory
ARG FUNCTION_DIR="/function"

FROM python:3.12 as build-image

# Include global arg in this stage of the build
ARG FUNCTION_DIR

# Copy function code
RUN mkdir -p ${FUNCTION_DIR}
COPY ./code ${FUNCTION_DIR}

# Install the function's dependencies
RUN pip install \
    --target ${FUNCTION_DIR} \
        awslambdaric

RUN pip3 install --target ${FUNCTION_DIR} psycopg2
RUN pip3 install --target ${FUNCTION_DIR} flask
RUN pip3 install --target ${FUNCTION_DIR} flask_cors
RUN pip3 install --target ${FUNCTION_DIR} boto3
RUN pip3 install --target ${FUNCTION_DIR} pymongo 

# Use a slim version of the base Python image to reduce the final image size

FROM python:3.12-slim

# Include global arg in this stage of the build
ARG FUNCTION_DIR
# Set working directory to function root directory
WORKDIR ${FUNCTION_DIR}
RUN apt-get update && apt-get install libpq5 -y
# Copy in the built dependencies
COPY --from=build-image ${FUNCTION_DIR} ${FUNCTION_DIR}

# Set runtime interface client as default command for the container runtime
ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
# Pass the name of the function handler as an argument to the runtime
CMD [ "lambda_function.handler" ]