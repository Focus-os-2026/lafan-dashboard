#!/bin/bash
# Exit on error
set -e

PROJECT_ID="focus-os-2026"
SERVICE_NAME="lafan-dashboard"
REGION="asia-southeast1"

echo "============================================="
echo "Deploying $SERVICE_NAME to Google Cloud Run..."
echo "Project: $PROJECT_ID"
echo "Region:  $REGION"
echo "============================================="

# Ensure we use the correct project
gcloud config set project $PROJECT_ID

# Deploy using Cloud Build (builds image from Dockerfile automatically and deploys)
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --allow-unauthenticated

echo "============================================="
echo "Deployment successful!"
echo "============================================="
