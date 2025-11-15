## Base information for Supabase application

Application name: Supabase
Homepage: https://supabase.com
GitHub page: https://github.com/supabase/supabase
Install instructions URL: https://supabase.com/docs/guides/self-hosting/docker
Category: dev
Dashboard Icon: supabase.png
Dashboard Group: Development
Short description: Open-source Postgres development platform with authentication, instant APIs, and realtime subscriptions
Long description: Supabase is a Postgres development platform built on enterprise-grade open source tools. It provides hosted Postgres database, authentication & authorization, auto-generated APIs (REST, GraphQL, and real-time subscriptions), serverless functions, file storage, and AI & vector toolkit for embeddings and semantic search.

## Container deployment

### Docker Compose Setup

Supabase provides an official Docker Compose setup in their GitHub repository. The deployment process involves:

1. Clone the official repository:
```bash
git clone --depth 1 https://github.com/supabase/supabase
```

2. Create a dedicated project directory and copy the Docker composition files:
```bash
mkdir supabase-project
cp -rf supabase/docker/* supabase-project
cp supabase/docker/.env.example supabase-project/.env
cd supabase-project
docker compose pull
docker compose up -d
```

### Environment Variables

The deployment relies on a `.env` file containing essential configuration variables:

#### Critical Security Settings
- **`POSTGRES_PASSWORD`**: Database authentication credential (must be changed from default)
- **`JWT_SECRET`**: Authentication token encryption key (must be changed from default)
- **`SITE_URL`**: Application base URL
- **`POOLER_TENANT_ID`**: Connection pooler identifier
- **`PG_META_CRYPTO_KEY`**: Studio-to-database encryption key
- **`SECRET_KEY_BASE`**: Communication security key (minimum 64 characters)

#### Dashboard Access Control
- **`DASHBOARD_USERNAME`**: Access control identifier (must be changed from default)
- **`DASHBOARD_PASSWORD`**: Authentication passphrase (must be changed from default)

#### Email Configuration
- **`SMTP_*` variables**: Email server configuration for authentication flows

### Service Access Points

The API gateway operates on port 8000, providing access to:
- REST API: `http://<your-ip>:8000/rest/v1/`
- Authentication: `http://<your-ip>:8000/auth/v1/`
- Storage: `http://<your-ip>:8000/storage/v1/`
- Realtime: `http://<your-ip>:8000/realtime/v1/`

### Database Connection

Supabase implements Supavisor as the connection pooler with two connection methods:
- Session-based connection: Port 5432
- Transactional pooling: Port 6543

### Technical Architecture

The platform combines several key components:
- **PostgreSQL**: Database foundation
- **PostgREST**: API generation
- **GoTrue**: Authentication service
- **Realtime**: Websocket subscriptions
- **Kong**: API gateway

### Security Considerations

**CRITICAL**: Default credentials must be changed before production deployment. The official documentation emphasizes: "you should NEVER deploy your Supabase setup using the defaults we have provided."

Key security practices:
1. Change all default passwords and secrets in the `.env` file
2. Use strong, randomly generated values for `JWT_SECRET`, `POSTGRES_PASSWORD`, and `SECRET_KEY_BASE`
3. Update dashboard authentication credentials
4. For production environments, implement a dedicated secrets manager (Doppler, Infisical, or cloud-native services) rather than relying on plaintext `.env` files
5. Ensure proper network security and firewall rules
6. Consider using a reverse proxy (like Traefik) with SSL/TLS termination

### Possible Further Improvements

1. **Reverse Proxy Integration**: Place Supabase behind Traefik for SSL/TLS termination and better routing
2. **Secrets Management**: Integrate with a secrets manager instead of using plaintext `.env` files
3. **Backup Strategy**: Implement automated PostgreSQL backups
4. **Monitoring**: Add Prometheus metrics and Grafana dashboards for service monitoring
5. **Resource Limits**: Set appropriate memory and CPU limits in the Docker Compose file
6. **Storage Volumes**: Configure persistent volumes for PostgreSQL data and storage buckets
7. **Email Service**: Configure SMTP settings for authentication emails (password reset, magic links, etc.)
8. **Custom Domain**: Configure a custom domain with SSL certificates
9. **Database Connection Pooling**: Optimize connection pooler settings based on expected load
10. **Health Checks**: Add Docker health checks for all services to ensure proper startup order
