#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}" python -m reservoirs.pipeline
