Open WebUI is an extensible, feature-rich, and user-friendly self-hosted WebUI for various LLM runners, supported LLM runners include Ollama and OpenAI-compatible APIs.

## References

- Home: [Open WebUI: Self-Hosted AI Platform](https://openwebui.com/)
- Source: [GitHub - open-webui/open-webui: User-friendly AI Interface (Supports Ollama, OpenAI API, ...)](https://github.com/open-webui/open-webui/)
- [Getting Started / Open WebUI](https://docs.openwebui.com/getting-started/)

Compose file based on: [open-webui/docker-compose.yaml at main · open-webui/open-webui](https://github.com/open-webui/open-webui/blob/main/docker-compose.yaml)

## Authentik

Open WebUI uses native OIDC for Authentik's `users` group. It redirects to
Authentik by default while retaining password authentication for recovery; use
`?form=1` on the login page to access the local form.

### Setup

Create `config/docker/<host>/open-webui/authentik-client-secret` with mode
`0600`. Set `OPEN_WEBUI_AUTHENTIK_CLIENT_ID`,
`OPEN_WEBUI_AUTHENTIK_CLIENT_SECRET` in ignored
`config/docker/<host>/.env.open-webui`, and set
`OPEN_WEBUI_AUTHENTIK_SIGNING_KEY` in the ignored host `.env`. The signing key
is an asymmetric Authentik certificate/key UUID used for ID-token validation.

```bash
scripts/authentik-apps.py --application open-webui --apply
scripts/labctl.py service recreate ai/open-webui
```

Keep the callback URI exact:
`https://open-webui.<domain>/oauth/oidc/callback`. Account merging by email
requires Authentik to provide verified, unique email addresses.

### Verify

Confirm an authorized user can sign in, a user outside `users` is denied, an
existing account links as intended, and local-password recovery still works.

## Backup

`backup.yaml` exports both `webui.db` and Chroma's SQLite DB online each night
under `${DB_BACKUP_ROOT}/ai-open-webui/`. B2 must pair them with
uploads, vectors, extensions and the pinned MiniLM archive outside the excluded
cache. Restore the original `WEBUI_SECRET_KEY`; model/settings changes require
updating the archive pin. See the [backup guide](../../../docs/backup.md) for
commands, retention and snapshot selection.

### Recovery

1. Stop the destination. Restore `database.sqlite3` as
   `/app/backend/data/webui.db` and `database-chroma.sqlite3` as
   `/app/backend/data/vector_db/chroma.sqlite3`; discard stale destination WAL/SHM.
2. Restore paired `uploads`, `docs`, vector index files, `functions`, `tools` and
   `litellm` state, plus original `WEBUI_SECRET_KEY` and OIDC settings. Start the
   matching application image. The SQLite exports and vector files are not an
   atomic capture, so check known document references after recovery.
3. For offline embedding, recover the revision referenced by the export's model
   metadata from `open-webui/offline-models/all-MiniLM-L6-v2/<revision>/` in the
   application snapshot. Verify `model.tar.gz` size/hash and contained file hashes
   against its `manifest.json`, then extract into a stable local directory; the
   archive contains a `model/` tree, including upstream model/license metadata.
4. Point `RAG_EMBEDDING_MODEL` to that local model directory and enable
   `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`. The restored persistent
   `rag.embedding_model` setting takes precedence over the environment; update
   it on the restored instance. `ENABLE_PERSISTENT_CONFIG=False` was an isolated
   drill alternative, not a required production recovery setting.

Local model retention preserves three recent revisions **plus every revision
referenced by retained DB exports**, and runs only after B2 coverage passes.

### Post-restore check

Restore both standalone SQLite exports and paired files; discard old DB WAL/SHM
sidecars before starting. Verify `/health`, open one historical chat/upload, and
run one known document query with a local model. For offline embedding, extract
the pinned archive, point the restored embedding setting at its local `model/`
directory, and enable Hugging Face offline mode. Follow the persistent-setting
steps above on the restored instance rather than changing the working instance.
