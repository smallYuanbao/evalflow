#!/usr/bin/env bash
set -e
mkdir -p data
uv run uvicorn backend.main:app --port 8000 --reload
