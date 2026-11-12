#!/usr/bin/env bash

set -e # exit on failure

# cd into script location
cd "$(dirname "$0")"
uv sync --extra discord
uv run --extra discord main.py
