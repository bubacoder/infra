#####################################################################
#                            Build Stage                            #
#####################################################################
FROM hugomods/hugo:exts as builder

# Set base URL
ARG HUGO_BASEURL
ENV HUGO_BASEURL=${HUGO_BASEURL}

# Install modules
COPY src/go.mod src/go.sum /src/
RUN hugo mod get

# Build site
COPY src/config.yaml /src/
COPY src/content/ /src/content/
RUN hugo --minify --gc

#####################################################################
#                            Final Stage                            #
#####################################################################
FROM hugomods/hugo:nginx
# Copy the generated files to keep the image as small as possible.
COPY --from=builder /public /site
