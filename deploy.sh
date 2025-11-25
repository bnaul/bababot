#!/bin/bash
set -e

PROJECT_ID="trumpbot-1470174245960"
REGION="us-central1"
SERVICE_NAME="bababot"

echo "Building and deploying Discord webhook handler to Cloud Run..."

# Build the container
gcloud builds submit --tag gcr.io/${PROJECT_ID}/${SERVICE_NAME} --project ${PROJECT_ID}

# Deploy as a Cloud Run service (serverless HTTP endpoint)
gcloud run deploy ${SERVICE_NAME} \
  --image gcr.io/${PROJECT_ID}/${SERVICE_NAME} \
  --region ${REGION} \
  --project ${PROJECT_ID} \
  --set-env-vars OPENAI_API_KEY=${OPENAI_API_KEY} \
  --set-env-vars DISCORD_PUBLIC_KEY=${DISCORD_PUBLIC_KEY} \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --min-instances 0 \
  --max-instances 10

echo ""
echo "✓ Deployed successfully!"
echo ""
echo "Your webhook URL:"
gcloud run services describe ${SERVICE_NAME} --region ${REGION} --project ${PROJECT_ID} --format 'value(status.url)'
echo ""
echo "Set this URL in Discord Developer Portal:"
echo "  Interactions Endpoint URL: [YOUR_URL]/discord/interactions"
