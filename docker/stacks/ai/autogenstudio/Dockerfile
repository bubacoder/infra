# kics-scan ignore-line - Missing User Instruction
FROM python:3.12-alpine
RUN apk -U upgrade --no-cache && \
    pip install --no-cache-dir autogenstudio==0.1.4

ENTRYPOINT ["autogenstudio", "ui", "--host", "0.0.0.0"]
