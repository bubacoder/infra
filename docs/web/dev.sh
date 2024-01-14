#!/bin/bash
set -euo pipefail

./update-docs.py

#(cd src && hugo serve --bind=0.0.0.0 --baseURL=http://0.0.0.0:1313)
docker run --rm -p 1313:1313 -v ./src:/src hugomods/hugo:exts hugo server --bind 0.0.0.0
