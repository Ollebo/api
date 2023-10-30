#!/bin/bash
kubectl create namespace dgraph
kubectl create --filename https://raw.githubusercontent.com/dgraph-io/dgraph/master/contrib/config/kubernetes/dgraph-single/dgraph-single.yaml -n dgraph

