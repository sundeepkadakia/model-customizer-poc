# Model Customizer MVP 0.3 — Cloud architecture

## Architecture

- **Frontend:** Vite/React, configured with `VITE_API_URL`.
- **Cloud Run:** stateless FastAPI control plane (`backend/app/main_cloud.py`).
- **Firestore:** projects + jobs.
- **Google Cloud Storage:** source datasets, normalized train/eval sets, LoRA adapters.
- **RunPod Serverless:** queue-based GPU worker (`worker/handler.py`) for train/evaluate/compare/generate.

The Cloud Run image contains no PyTorch stack. GPU dependencies live only in the RunPod worker image, keeping API cold starts and costs small.

## 1. GCP bootstrap

```bash
export PROJECT_ID="YOUR_PROJECT_ID"
export REGION="us-west1"
export BUCKET="${PROJECT_ID}-model-customizer"

gcloud auth login
gcloud projects list
gcloud config set project "$PROJECT_ID"
#gcloud config list

# Make sure you are using the correct gcloud configuration
#gcloud config configurations list
#gcloud config configurations activate modelcustomizerplatform
gcloud auth application-default login

gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com firestore.googleapis.com storage.googleapis.com secretmanager.googleapis.com

gcloud storage buckets create "gs://$BUCKET" --location="$REGION" --uniform-bucket-level-access
# Create Firestore Native database once in Console, or:
gcloud firestore databases create --location="$REGION" --type=firestore-native
```

Create a Cloud Run service account and grant only what the API needs:

```bash
gcloud iam service-accounts create model-customizer-api
API_SA="model-customizer-api@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$API_SA" --role="roles/datastore.user"
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member="serviceAccount:$API_SA" --role="roles/storage.objectAdmin"
```

Store RunPod API key in Secret Manager:

```bash
printf '%s' 'YOUR_RUNPOD_API_KEY' | gcloud secrets create runpod-api-key --data-file=-
gcloud secrets add-iam-policy-binding runpod-api-key --member="serviceAccount:$API_SA" --role="roles/secretmanager.secretAccessor"
```

## 2. RunPod worker

Build and push `worker/` to Docker Hub (or any registry RunPod can pull):

```bash
cd worker
docker build -t YOUR_DOCKERHUB/model-customizer-worker:0.3 .
docker push YOUR_DOCKERHUB/model-customizer-worker:0.3
```

In RunPod Serverless create a **Queue-based** endpoint using this image. Start with a 24 GB GPU class and **Active workers = 0**, **Max workers = 1**. Increase execution timeout for training jobs.

The worker needs access to the GCS bucket. For this MVP, create a *separate bucket-scoped service account* with `roles/storage.objectAdmin`, store its JSON as a RunPod secret named `GCP_SERVICE_ACCOUNT_JSON`. The worker reads the JSON directly from that environment variable. Do not reuse your personal credentials. Replace this with workload federation later.

## 3. Deploy API to Cloud Run

```bash
cd backend
export RUNPOD_ENDPOINT_ID="YOUR_ENDPOINT_ID"

gcloud run deploy model-customizer-api \
  --source . \
  --region "$REGION" \
  --service-account "$API_SA" \
  --allow-unauthenticated \
  --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,GCS_BUCKET=$BUCKET,RUNPOD_ENDPOINT_ID=$RUNPOD_ENDPOINT_ID,CORS_ORIGINS=http://localhost:5173" \
  --set-secrets "RUNPOD_API_KEY=runpod-api-key:latest" \
  --command uvicorn \
  --args app.main_cloud:app,--host,0.0.0.0,--port,8080
```

The backend directory includes a `Dockerfile`, so Cloud Run source deployment uses the lightweight cloud requirements rather than the local ML requirements.

## 4. Frontend

Set the deployed Cloud Run URL:

```bash
cd frontend
printf 'VITE_API_URL=https://YOUR_CLOUD_RUN_URL\n' > .env.production
npm run build
```

Deploy the `dist/` folder to your preferred static host.

## Important MVP notes

1. RunPod async results are polled through `GET /jobs/{id}`. The frontend polls while a job is active.
2. Adapter and dataset bytes never pass through Firestore; Firestore stores metadata and GCS URIs only.
3. Cloud Run is stateless. No SQLite or local adapter directory is required in cloud mode.
4. The worker downloads models from Hugging Face on cold start. Use RunPod network volume/model caching before production traffic.
5. Add authentication before giving the app to external users. `--allow-unauthenticated` is only for the MVP.
