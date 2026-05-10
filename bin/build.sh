#!/bin/bash
set -e
pip install -r requirements.txt
apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-chi-sim 2>/dev/null || true
pip install pytesseract whoosh 2>/dev/null || true
