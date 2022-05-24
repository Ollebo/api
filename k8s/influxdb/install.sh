#!/bin/bash
kubectl create namespace influxdb
kubectl apply -f deploy.yaml -n influxdb

