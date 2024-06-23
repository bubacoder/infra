#####################################################################
#                            Build Stage                            #
#####################################################################
FROM hugomods/hugo:exts AS builder

# Set base URL
ARG HUGO_BASEURL
ENV HUGO_BASEURL=${HUGO_BASEURL}

# Install modules
COPY src/go.mod src/go.sum /src/
COPY src/config.module.yaml /src/config.yaml
RUN hugo mod get

# Build site
COPY src/config.yaml /src/
COPY src/content/ /src/content/
COPY src/layouts/ /src/layouts/
RUN hugo --minify --gc

#####################################################################
#                            Final Stage                            #
#####################################################################
FROM hugomods/hugo:nginx
# Copy the generated files to keep the image as small as possible.
COPY --from=builder /public /site
