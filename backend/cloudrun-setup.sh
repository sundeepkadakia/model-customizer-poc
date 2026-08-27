gcloud auth login
gcloud auth application-default login
gcloud config configurations list
gcloud config list
#
# This script sets up the Google Cloud Run environment for the Model Customizer Platform.
#   
gcloud projects add-iam-policy-binding modelcustomizerplatform \
  --member="serviceAccount:model-customizer-api@modelcustomizerplatform.iam.gserviceaccount.com" \
  --role="roles/datastore.user"
#
# Create a secret in GCP Secret Manager to store the RunPod API key
#
printf '%s' 'YOUR_RUNPOD_API_KEY' | \
gcloud secrets create runpod-api-key \
  --data-file=- \
  --replication-policy=automatic
#
# Grant the service account permission to access the secret
#
gcloud secrets add-iam-policy-binding runpod-api-key \
  --member="serviceAccount:model-customizer-api@modelcustomizerplatform.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
#
# Build the docker image for the backend API
#
docker build \
  -t us-west1-docker.pkg.dev/modelcustomizerplatform/model-customizer/model-customizer-api:v0.1 \
  .
#
# Push the docker image to GCP Artifact Registry
#
docker push \
  us-west1-docker.pkg.dev/modelcustomizerplatform/model-customizer/model-customizer-api:v0.1
#
# Build for Cloud Run’s Linux architecture. That combines build + push and avoids architecture surprises.
# 
docker buildx build \
  --platform linux/amd64 \
  -t us-west1-docker.pkg.dev/modelcustomizerplatform/model-customizer/model-customizer-api:v0.2 \
  --push \
  .

#
# Deploy the backend API to Google Cloud Run
#
gcloud run deploy model-customizer-api \
  --image us-west1-docker.pkg.dev/modelcustomizerplatform/model-customizer/model-customizer-api:v0.2 \
  --region us-west1 \
  --service-account="model-customizer-api@modelcustomizerplatform.iam.gserviceaccount.com" \
  --set-env-vars="^@^GCP_PROJECT_ID=modelcustomizerplatform@GCS_BUCKET=model-customizer-dev@RUNPOD_ENDPOINT_ID=yuuyg0gfkccm1n@CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173" \
  --set-secrets="RUNPOD_API_KEY=runpod-api-key:latest" \
  --allow-unauthenticated
#
# Service URL: https://model-customizer-api-1093076713830.us-west1.run.app
#
gcloud run services describe model-customizer-api \
  --region us-west1
# 
gcloud run services logs read model-customizer-api \
  --region us-west1 \
  --limit 50
#
# Scale the backend API to 0-1 instances to save costs when idle
#
gcloud run services update model-customizer-api \
  --region=us-west1 \
  --min=0 \
  --max=1