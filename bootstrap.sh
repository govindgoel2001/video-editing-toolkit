#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo 'Install FFmpeg and ffprobe first (brew install ffmpeg or apt install ffmpeg).'; exit 1; }
command -v node >/dev/null || { echo 'Install Node.js 22+ first.'; exit 1; }
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[video-use]'
npm ci
.venv/bin/python toolkit.py doctor
echo 'Ready. Try: .venv/bin/python toolkit.py demo --graphics'
