# RRS Pipeline - Setup Guide

## Prerequisites
Before deploying, you need to create the GCP project and replace the placeholder.

### 1. Find & Replace Project ID
Once you create your GCP project, do a find-and-replace across all files:
- **Find:** `YOUR_RRS_PROJECT_ID`
- **Replace with:** your actual GCP project ID (e.g., `landairsea-rrs`)  LandAirSea-RRS

Files that contain the placeholder:
- `cloudbuild.yaml` (5 occurrences)
- `main.py` (1 occurrence)

### 2. Enable Required APIs
```bash
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    secretmanager.googleapis.com \
    bigquery.googleapis.com \
    cloudscheduler.googleapis.com \
    --project=YOUR_RRS_PROJECT_ID
```

### 3. Create Secrets in Secret Manager
Store the RRS LandAirSea credentials (these are different from the ACME credentials):
```bash
echo -n "YOUR_RRS_CLIENT_TOKEN" | gcloud secrets create rrs-client-token \
    --data-file=- --project=YOUR_RRS_PROJECT_ID

echo -n "YOUR_RRS_USERNAME" | gcloud secrets create rrs-username \
    --data-file=- --project=YOUR_RRS_PROJECT_ID

echo -n "YOUR_RRS_PASSWORD" | gcloud secrets create rrs-password \
    --data-file=- --project=YOUR_RRS_PROJECT_ID
```

### 4. Create BigQuery Dataset & Table
```bash
# Create dataset
bq mk --dataset YOUR_RRS_PROJECT_ID:LAS_RRS_deviceLocations

# Create table
bq mk --table YOUR_RRS_PROJECT_ID:LAS_RRS_deviceLocations.rrs_device_locations \
    record_id:STRING,data_timestamp:TIMESTAMP,device_id:STRING,latitude:FLOAT,longitude:FLOAT,last_location:STRING,speed_kmh:FLOAT,heading:FLOAT,elevation:FLOAT,voltage:FLOAT,is_stopped:BOOLEAN,cellular_strength:INTEGER,satellite_strength:INTEGER,interval:INTEGER,last_location_timestamp:STRING
```

### 5. Create Service Account & Grant Permissions
```bash
# Create service account
gcloud iam service-accounts create landairsea-rrs-pipeline \
    --display-name="LandAirSea RRS Pipeline" \
    --project=YOUR_RRS_PROJECT_ID

SERVICE_ACCOUNT="landairsea-rrs-pipeline@YOUR_RRS_PROJECT_ID.iam.gserviceaccount.com"

# Grant BigQuery permissions
gcloud projects add-iam-policy-binding YOUR_RRS_PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding YOUR_RRS_PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding YOUR_RRS_PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/bigquery.readSessionUser"

# Grant Secret Manager access
gcloud projects add-iam-policy-binding YOUR_RRS_PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor"

# Grant Cloud Run invoker (for scheduler)
gcloud projects add-iam-policy-binding YOUR_RRS_PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/run.invoker"
```

### 6. Deploy via Cloud Build
```bash
# Connect your GitHub repo first in Cloud Console > Cloud Build > Triggers
# Then push to trigger a build, or manually:
gcloud builds submit --config cloudbuild.yaml --project=YOUR_RRS_PROJECT_ID
```

### 7. Set Up Cloud Scheduler (every 5 minutes)
```bash
CLOUD_RUN_URL=$(gcloud run services describe landairsea-rrs-pipeline \
    --platform managed \
    --region us-central1 \
    --format 'value(status.url)' \
    --project=YOUR_RRS_PROJECT_ID)

gcloud scheduler jobs create http landairsea-rrs-pipeline-job \
    --schedule="*/5 * * * *" \
    --uri="$CLOUD_RUN_URL" \
    --http-method=POST \
    --oidc-service-account-email="landairsea-rrs-pipeline@YOUR_RRS_PROJECT_ID.iam.gserviceaccount.com" \
    --oidc-token-audience="$CLOUD_RUN_URL" \
    --location=us-central1 \
    --project=YOUR_RRS_PROJECT_ID
```

### 8. Test the Pipeline
```bash
# Manual test
curl -X POST \
    -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
    $CLOUD_RUN_URL
```

## Key Differences from ACME Stack
| Resource | ACME Stack | RRS Stack |
|---|---|---|
| GCP Project | `landairsea-trackmydevice` | `YOUR_RRS_PROJECT_ID` |
| Cloud Run Service | `landairsea-pipeline` | `landairsea-rrs-pipeline` |
| BigQuery Dataset | `LAS_deviceLocations` | `LAS_RRS_deviceLocations` |
| BigQuery Table | `device_locations` | `rrs_device_locations` |
| Secret: Token | `landairsea-client-token` | `rrs-client-token` |
| Secret: Username | `landairsea-username` | `rrs-username` |
| Secret: Password | `landairsea-password` | `rrs-password` |
| ClientId Header | `pipeline-client` | `rrs-pipeline-client` |
| Scheduler Job | `landairsea-pipeline-job2` | `landairsea-rrs-pipeline-job` |
