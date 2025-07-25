#####################################################################
#           Collect and convert Markdown and Compose files          #
#####################################################################
FROM python:3.13-alpine3.22 AS collect

WORKDIR /tmp
COPY docs/web/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Note: Add parameter for verbose output: --verbose
RUN --mount=type=bind,ro,source=.,target=/repo /repo/docs/web/update-docs.py --repository-path /repo --output-content-path /src/content

#####################################################################
#                            Build Stage                            #
#####################################################################
FROM hugomods/hugo:exts-0.148.1 AS build

# Set base URL
ARG HUGO_BASEURL
ENV HUGO_BASEURL=${HUGO_BASEURL}

# Install modules
COPY docs/web/src/go.mod docs/web/src/go.sum /src/
COPY docs/web/src/config.module.yaml /src/config.yaml
RUN hugo mod get

# Build site
COPY docs/web/src/config.yaml /src/
COPY docs/web/src/layouts/ /src/layouts/
COPY --from=collect /src/content/ /src/content/
RUN hugo --minify --gc

#####################################################################
#                            Final Stage                            #
#####################################################################
# User "nginx" is specified in /etc/nginx/nginx.conf
# kics-scan ignore-line - Missing User Instruction
FROM hugomods/hugo:nginx-1.29.0

COPY --from=build /public /site
