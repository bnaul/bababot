#!/bin/bash
set -e

PROJECT_ID="trumpbot-1470174245960"
ZONE="us-central1-a"  # Free tier eligible zone
INSTANCE_NAME="bababot"

echo "Creating Compute Engine VM in free tier..."

# Create a startup script file
cat > /tmp/startup-script.sh <<'STARTUPEOF'
#!/bin/bash
set -e

# Update system
apt-get update
apt-get install -y python3-pip git

# Create app directory
mkdir -p /opt/bababot
cd /opt/bababot

# Get code from git
if [ ! -d ".git" ]; then
    git init
    git remote add origin https://github.com/bnaul/bababot.git || true
    git fetch origin
    git checkout -f origin/main
else
    git fetch origin
    git checkout -f origin/main
fi

# Install dependencies
pip3 install -r requirements.txt

# Get environment variables from metadata
DISCORD_TOKEN=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/attributes/discord-token" -H "Metadata-Flavor: Google")
OPENAI_API_KEY=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/attributes/openai-key" -H "Metadata-Flavor: Google")

export DISCORD_TOKEN
export OPENAI_API_KEY

# Run the bot with auto-restart
while true; do
    echo "Starting bababot..."
    python3 main.py || echo "Bot crashed, restarting in 5 seconds..."
    sleep 5
done
STARTUPEOF

# Create the VM
gcloud compute instances create ${INSTANCE_NAME} \
    --project=${PROJECT_ID} \
    --zone=${ZONE} \
    --machine-type=e2-micro \
    --network-interface=network-tier=STANDARD,stack-type=IPV4_ONLY,subnet=default \
    --metadata-from-file=startup-script=/tmp/startup-script.sh \
    --metadata=discord-token="${DISCORD_TOKEN}",openai-key="${OPENAI_API_KEY}" \
    --maintenance-policy=MIGRATE \
    --provisioning-model=STANDARD \
    --service-account=1066095051534-compute@developer.gserviceaccount.com \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    --create-disk=auto-delete=yes,boot=yes,device-name=${INSTANCE_NAME},image=projects/debian-cloud/global/images/debian-12-bookworm-v20241112,mode=rw,size=10,type=pd-standard \
    --no-shielded-secure-boot \
    --shielded-vtpm \
    --shielded-integrity-monitoring \
    --labels=goog-ec-src=vm_add-gcloud \
    --reservation-affinity=any

echo ""
echo "✓ VM created successfully!"
echo ""
echo "The bot will start automatically in a few minutes."
echo ""
echo "To view logs:"
echo "  gcloud compute ssh ${INSTANCE_NAME} --zone=${ZONE} --project=${PROJECT_ID} --command='sudo journalctl -u google-startup-scripts -f'"
echo ""
echo "To stop the VM:"
echo "  gcloud compute instances stop ${INSTANCE_NAME} --zone=${ZONE} --project=${PROJECT_ID}"
echo ""
echo "To delete the VM:"
echo "  gcloud compute instances delete ${INSTANCE_NAME} --zone=${ZONE} --project=${PROJECT_ID}"

rm /tmp/startup-script.sh
