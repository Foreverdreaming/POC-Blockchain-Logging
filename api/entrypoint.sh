#!/bin/sh
set -e

echo "Waiting for deployed.json..."
until [ -s "${DEPLOYED_JSON_PATH:-/artifacts/deployed.json}" ]; do
  sleep 1
done

echo "Starting API..."
exec python flask_server.py
