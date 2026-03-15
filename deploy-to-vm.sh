#!/bin/bash
# Script to deploy agent to VM
# Run this from your local machine after setting VM_PASSWORD

VM_USER="operator"
VM_HOST="10.93.25.181"
VM_PASS="1234"
PROJECT_DIR="~/se-toolkit-lab-6"

echo "=== Deploying agent to VM ==="

# Option 1: If repo already exists on VM, update it
echo "Checking if repo exists on VM..."
sshpass -p "$VM_PASS" ssh -o StrictHostKeyChecking=no "$VM_USER@$VM_HOST" "
    if [ -d '$PROJECT_DIR' ]; then
        echo 'Repo exists, updating...'
        cd $PROJECT_DIR
        git fetch origin
        git checkout 1234
        git pull origin 1234
    else
        echo 'Repo not found, cloning...'
        cd ~
        git clone https://github.com/YOUR_GITHUB_USERNAME/se-toolkit-lab-6
        cd se-toolkit-lab-6
        git checkout 1234
    fi
"

# Copy environment files
echo "Copying environment files..."
sshpass -p "$VM_PASS" scp -o StrictHostKeyChecking=no .env.agent.secret "$VM_USER@$VM_HOST:$PROJECT_DIR/"
sshpass -p "$VM_PASS" scp -o StrictHostKeyChecking=no .env.docker.secret "$VM_USER@$VM_HOST:$PROJECT_DIR/"

# Test the agent
echo "Testing agent on VM..."
sshpass -p "$VM_PASS" ssh -o StrictHostKeyChecking=no "$VM_USER@$VM_HOST" "
    cd $PROJECT_DIR
    echo 'Running test question...'
    python agent.py 'What is 2+2?'
"

echo "=== Deployment complete ==="
