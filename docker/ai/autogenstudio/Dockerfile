# kics-scan ignore-line - Missing User Instruction
FROM python:3.14-slim

# Package: https://pypi.org/project/autogenstudio/
RUN pip install --no-cache-dir --upgrade autogenstudio==0.4.2.2

EXPOSE 8081
ENTRYPOINT ["autogenstudio", "ui", "--host", "0.0.0.0", "--port", "8081"]
