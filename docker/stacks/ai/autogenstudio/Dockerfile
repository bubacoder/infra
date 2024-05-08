
FROM python:3.11-alpine
RUN apk -U upgrade --no-cache
RUN pip install autogenstudio

ENTRYPOINT ["autogenstudio", "ui", "--host", "0.0.0.0"]
