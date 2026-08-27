
gcloud auth login
gcloud auth application-default login
gcloud config configurations list
gcloud config list

#
# Following steps are needed to push the docker image to GCP Artifact Registry - once per project
#
gcloud artifacts repositories create model-customizer \
  --repository-format=docker \
  --location=us-west1 \
  --description="Docker images for Model Customizer"

gcloud auth configure-docker us-west1-docker.pkg.dev

#
# Create a dedicated service account
#
gcloud iam service-accounts create runpod-artifact-reader \
  --display-name="RunPod Artifact Registry Reader"
#
# Grant the service account permission to read from Artifact Registry
#
gcloud artifacts repositories add-iam-policy-binding model-customizer \
  --location=us-west1 \
  --member="serviceAccount:runpod-artifact-reader@modelcustomizerplatform.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.reader"
#
# Grant the service account permission to read/write to the GCS bucket
#
gcloud storage buckets add-iam-policy-binding \
  gs://model-customizer-dev \
  --member="serviceAccount:model-customizer-api@modelcustomizerplatform.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
#
# Create a service account key for the service account
#
gcloud iam service-accounts keys create model-customizer-api-key.json \
  --iam-account=model-customizer-api@modelcustomizerplatform.iam.gserviceaccount.com

#
# Build the docker image for the worker
#
docker build --platform=linux/amd64 -t model-customizer-worker:0.1 .
#
# Following steps are needed to push the docker image to GCP Artifact Registry - once per image
#  Use runpod-worker:v0.1 instead of latest to avoid caching issues when pushing new images with the same tag
docker build \
  -t us-west1-docker.pkg.dev/modelcustomizerplatform/model-customizer/runpod-worker:v0.1 \
  .
#
# Push the docker image to GCP Artifact Registry
#
docker push us-west1-docker.pkg.dev/modelcustomizerplatform/model-customizer/runpod-worker:v0.1
#
# List the docker images in GCP Artifact Registry
#
gcloud artifacts docker images list \
  us-west1-docker.pkg.dev/modelcustomizerplatform/model-customizer \
  --include-tags
#
# Delete the docker image from GCP Artifact Registry
#
gcloud artifacts docker images delete \
  us-west1-docker.pkg.dev/modelcustomizerplatform/model-customizer/runpod-worker@sha256:3dc4648507af7d8360a04bdf14475bd0fb808174f52a9799e4a9351b7b3b8447
#
# Create a RunPod template for the worker
#
curl --request POST \
  --url https://rest.runpod.io/v1/templates \
  --header "Authorization: Bearer rpa_BXXTWOK5G8RH0P73T9VHZWEBK6G79VJGAYVX4TFW176295" \
  --header "Content-Type: application/json" \
  --data '{
    "name": "model-customizer-worker",
    "imageName": "us-west1-docker.pkg.dev/modelcustomizerplatform/model-customizer/runpod-worker:latest",
    "category": "NVIDIA",
    "containerDiskInGb": 20,
    "containerRegistryAuthId": "cmt24krp7004m14j6qczmj763",
    "dockerEntrypoint": [],
    "dockerStartCmd": [],
    "env": {},
    "isPublic": false,
    "isServerless": true
  }'
#
# Response:
#
#{"category":"NVIDIA","config":{"templateId":"ogdpe91lp6"},"containerDiskInGb":20,"containerRegistryAuthId":"cmt24krp7004m14j6qczmj763","id":"ogdpe91lp6","imageName":"us-west1-docker.pkg.dev/modelcustomizerplatform/model-customizer/runpod-worker:latest","isServerless":true,"name":"model-customizer-worker","ports":["8888/http","22/tcp"],"readme":"","startJupyter":true,"startSsh":true,"volumeMountPath":"/workspace"}
#
# Create a RunPod endpoint for the worker
#
curl --request POST \
  --url https://rest.runpod.io/v1/endpoints \
  --header "Authorization: Bearer rpa_BXXTWOK5G8RH0P73T9VHZWEBK6G79VJGAYVX4TFW176295" \
  --header "Content-Type: application/json" \
  --data '{
    "templateId": "ogdpe91lp6",
    "name": "model-customizer",
    "computeType": "GPU",
    "gpuCount": 1,
    "workersMin": 0,
    "workersMax": 1,
    "idleTimeout": 5,
    "executionTimeoutMs": 3600000
  }'

curl -i \
  --request GET \
  --url https://rest.runpod.io/v1/endpoints \
  --header "Authorization: Bearer rpa_BXXTWOK5G8RH0P73T9VHZWEBK6G79VJGAYVX4TFW176295"

curl --request POST \
  --url https://rest.runpod.io/v1/endpoints \
  --header "Authorization: Bearer rpa_BXXTWOK5G8RH0P73T9VHZWEBK6G79VJGAYVX4TFW176295" \
  --header "Content-Type: application/json" \
  --data '{
    "templateId": "ogdpe91lp6"
  }'

#
# Start the FastAPI application
python -m uvicorn app.main_cloud:app --reload --port 8000
#
# Build and push the Docker image
#   
docker buildx build \
  --platform linux/amd64 \
  -t us-west1-docker.pkg.dev/modelcustomizerplatform/model-customizer/runpod-worker:v0.3 \
  --push \
  .