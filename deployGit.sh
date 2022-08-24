#!/bin/bash
#
#
# Simple script to clone and update deploy repo for gitops
#
#
export GITSHA=$(git rev-parse HEAD)
echo "Getting the deploy repo"
git clone $GITREPO /deploy

echo "Create template files"
helm template --set SHA=$GITSHA --dry-run chart/ >> /deploy/$GITFOLDER/deploy.yaml


echo "Commit and push"
cd /deploy
git add $GITFOLDER
git commit -a -m "Deploy $GITSHA"
git push origin main 


echo "Alle done"

