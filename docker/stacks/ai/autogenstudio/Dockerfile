
FROM python:3.11-alpine
RUN apk -U upgrade --no-cache && \
    pip install --no-cache-dir autogenstudio

ENTRYPOINT ["autogenstudio", "ui", "--host", "0.0.0.0"]
