#!/bin/sh
set -x
echo "[SHELL] Starting..."
python entrypoint.py
exit $?
