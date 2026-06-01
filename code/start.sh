#!/bin/bash
export LC_ALL=C.UTF-8
export LANG=C.UTF-8

exec gunicorn -w 1 --threads 16 -k gthread -b 0.0.0.0:8080 \
     --timeout 0 --graceful-timeout 30 start:app
