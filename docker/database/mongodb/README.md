MongoDB is a source-available, document-oriented NoSQL database designed for scalability and
developer agility, storing data as flexible, JSON-like documents rather than rows and columns.

This is a shared instance, following the same pattern as postgresql/couchdb in this category.
Mongo's /docker-entrypoint-initdb.d scripts only run once, on first startup with an empty data
directory — each consuming service should add its own init script under ./config/initdb when it
first starts using this instance. A service added *after* this instance already has data must
create its user/db manually via `mongosh` instead, since init scripts won't re-run.

Links:
- Home: https://www.mongodb.com
- Source: https://github.com/docker-library/mongo
- Docs: https://hub.docker.com/_/mongo

TODO: Add a mongo-express (or similar) admin UI service if a web GUI is wanted
TODO: Implement an automated backup solution (mongodump)
