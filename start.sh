#!/bin/bash
# Start script for cloud deployment (Render, Railway, Koyeb)

# Ensure the script exits on error
set -e

# Run the FastAPI server
# Note: DO NOT use uvicorn with self-signed certs in the cloud,
# the cloud provider (Render/Railway) handles HTTPS networking for us automatically.
echo "Starting Alita AI Partner on port $PORT..."
python main.py
