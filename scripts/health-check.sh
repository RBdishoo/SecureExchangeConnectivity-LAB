#!/usr/bin/env bash
# Week 1 scaffold — expanded in later weeks.
set -euo pipefail
echo "Checking gateway health on localhost:8080..."
curl -sf "http://localhost:8080/health" && echo && echo "OK"
