# kics-scan ignore-line - Missing User Instruction
FROM python:3.13-alpine

# hadolint ignore=DL3018
RUN apk -U upgrade --no-cache && \
    apk add --no-cache gcc musl-dev geos-dev && \
    pip install --no-cache-dir autogenstudio==0.1.5

ENTRYPOINT ["autogenstudio", "ui", "--host", "0.0.0.0"]
