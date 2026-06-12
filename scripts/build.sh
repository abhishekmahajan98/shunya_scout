#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Building frontend..."
cd frontend
npm ci
npm run build

echo "Build complete. Frontend output: frontend/dist"
