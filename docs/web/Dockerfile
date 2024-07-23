#####################################################################
#           Collect and convert Markdown and Compose files          #
#####################################################################
FROM python:3.12-alpine3.20 AS collect

COPY docs/web/requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . /repo

# Note: Add parameter for verbose output: --verbose
RUN /repo/docs/web/update-docs.py --repository-root /repo

#####################################################################
#                            Build Stage                            #
#####################################################################
FROM hugomods/hugo:exts-0.129.0 AS build

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
COPY --from=collect /repo/docs/web/src/content/ /src/content/
RUN hugo --minify --gc

#####################################################################
#                            Final Stage                            #
#####################################################################
FROM hugomods/hugo:nginx-1.27.0

COPY --from=build /public /site
