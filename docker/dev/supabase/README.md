Open-source Postgres development platform with authentication, instant APIs, and realtime subscriptions.
Supabase provides hosted Postgres database, authentication & authorization, auto-generated APIs
(REST, GraphQL, and real-time subscriptions), serverless functions, file storage, and AI & vector
toolkit for embeddings and semantic search.

Links:
- Home: https://supabase.com
- Source: [GitHub - supabase/supabase: The Postgres development platform. Supabase gives you a dedicated Postgres database to build your web, mobile, and AI applications.](https://github.com/supabase/supabase)
- Docs: https://supabase.com/docs/guides/self-hosting/docker
- Docker Setup: [supabase/docker at master · supabase/supabase](https://github.com/supabase/supabase/tree/master/docker)

Note: The self-hosted version supports only one project - [Creating multiple organizations and/or projects for self-hosted deployments · supabase · Discussion #4907](https://github.com/orgs/supabase/discussions/4907)

TODO: Configure SMTP settings for authentication emails (password reset, magic links, etc.)
TODO: Consider implementing automated PostgreSQL backups
TODO: Add Prometheus metrics and Grafana dashboards for service monitoring
TODO: Optimize connection pooler settings based on expected load
