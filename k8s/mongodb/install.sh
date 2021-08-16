#!/bin/bash
echo "Install mongodb into cluster"


helm repo add bitnami https://charts.bitnami.com/bitnami
kubectl create namespace mongodb 
helm upgrade --install  mongodb bitnami/mongodb -f values.yaml -n mongodb
