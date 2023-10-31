docker run \
    -v "$HOME"/.config/gcloud:/root/.config/gcloud \
    -v /home/mattias/projects/ollebo/api:/workspace \
    gcr.io/kaniko-project/executor:latest \
    --dockerfile /workspace/Dockerfile \
    --destination "docker.io/ollebo/api" \
    --context dir:///workspace/ --no-push 
