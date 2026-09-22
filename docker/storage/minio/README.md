MinIO is a high-performance, S3 compatible object store

The MinIO deployment starts using default root credentials `${ADMIN_USER}:${ADMIN_PASSWORD}`. You can test the deployment using the MinIO Console, an embedded object browser built into MinIO Server.
Point a web browser to `https://minio-console.${MYDOMAIN}` and log in with the root credentials. You can use the Browser to create buckets, upload objects, and browse the contents of the MinIO server.
You can also connect using any S3-compatible tool, such as the MinIO Client mc commandline tool. See Test using MinIO Client mc for more information on using the mc commandline tool.
For application developers, see https://min.io/docs/minio/linux/developers/minio-drivers.html to view MinIO SDKs for supported languages.

For example, consider a MinIO deployment behind a proxy https://minio.example.net, https://console.minio.example.net with rules for forwarding traffic on port :9000 and :9001 to MinIO and the MinIO Console respectively
on the internal network. Set `MINIO_BROWSER_REDIRECT_URL` to https://console.minio.example.net to ensure the browser receives a valid reachable URL.
Similarly, if your TLS certificates do not have the IP SAN for the MinIO server host, the MinIO Console may fail to validate the connection to the server. Use the MINIO_SERVER_URL environment variable and specify the proxy-accessible hostname of the MinIO server to allow the Console to use the MinIO server API using the TLS certificate.
For example: `export MINIO_SERVER_URL="https://minio.example.net"`

Links:
- Home: https://min.io
- Compose: https://github.com/minio/minio/blob/master/docs/orchestration/docker-compose/docker-compose.yaml
