---
description: Update AI model configurations to use the latest model versions from each provider
---

Update the AI model configurations to use the latest available model IDs, removing outdated versions. This includes the LiteLLM config, the Ollama model list in the Taskfile, and syncing LiteLLM's local Ollama entries.

## Config file locations

Read the current LiteLLM config via:
```bash
docker exec litellm cat /app/config.yaml
```

Source files:
- `docker/ai/litellm/config/config.yaml` — LiteLLM model list
- `Taskfile.yaml` — Ollama models are listed in the `get-offline-data-ollama` task

## Step 1: Look up latest models per provider (run searches in parallel)

Search the web for the current model IDs for each provider present in the config:

- **Anthropic**: Search "Anthropic Claude latest models API model IDs" → check https://docs.anthropic.com/en/docs/about-claude/models/overview
- **OpenAI**: Search "OpenAI latest models API model IDs" → check https://platform.openai.com/docs/models
- **Google Gemini**: Search "Google Gemini latest models API model IDs" → check https://ai.google.dev/gemini-api/docs/models
- **OpenRouter (Meta Llama)**: Search "Meta Llama latest models openrouter model IDs"
- **OpenRouter (DeepSeek)**: Search "DeepSeek latest models openrouter model IDs"
- **OpenRouter (xAI Grok)**: Search "xAI Grok latest models openrouter model IDs"
- **Ollama local (≤3B)**: Search "best 3B LLM model Ollama <year> benchmark" → check https://ollama.com/library
- **Ollama local (≤8B)**: Search "best 8B LLM model Ollama <year> benchmark" → check https://ollama.com/library

For each provider, identify:
1. The **latest stable** model ID (not preview/experimental unless that's the only option)
2. Whether the currently configured model has been **superseded** by a newer release
3. The **exact API model ID string** to use in LiteLLM params

For Ollama local models, pick the **best-performing model** in each size class based on current benchmarks (HumanEval, MMLU, etc.), not just the newest release date.

## Step 2: Determine what to change

### LiteLLM cloud models

For each model in the config, decide:
- **Add**: A newer stable version exists → add a new entry with the updated `model_name` and `litellm_params.model`
- **Keep (latest)**: Already the most recent stable model → no change
- **Keep (previous)**: One version behind the latest → keep as-is (allows pinning to the prior version)
- **Remove**: Two or more versions behind the latest → remove to avoid clutter

Example (illustrates the rule — do not treat these version numbers as current): config has Opus 4.5 and 4.6 → Opus 4.7 released → add 4.7, keep 4.6, remove 4.5. Apply the "latest / one-behind / two-or-more-behind" rule against the versions you actually find in Step 1, not against the numbers written here or already in the config.

Preserve without changes:
- The overall YAML structure, comments, and provider groupings
- `api_key` and `api_base` references

### Ollama local models (`Taskfile.yaml` → `get-offline-data-ollama` task)

The task must always include exactly:
- **One model ≤3B** — best benchmark performer in this size class (e.g. `phi4-mini`)
- **One model ≤8B** — best benchmark performer in this size class (e.g. `qwen3:8b`)
- **Embedding models** — keep as-is unless a clearly better alternative exists

Update both the `docker exec ollama ollama pull <model>` lines and the inline comments with model size.

### LiteLLM Ollama entries sync

After updating the Taskfile, make the `ollama-local-*` entries in `config.yaml` match it **one-to-one**: there must be exactly one `ollama-local-*` entry per model pulled by the task. If the task pulls a model that has no matching entry, **add** the missing entry; if an entry points to a model no longer pulled, remove it.
- **Chat models** (the ≤3B and ≤8B entries): `ollama_chat/<model>` must reflect the exact tag used in the pull script.
- **Embedding models** (e.g. `nomic-embed-text`): use the `ollama/<model>:latest` prefix, not `ollama_chat/` — LiteLLM routes `ollama_chat/` to the chat-completions endpoint, which doesn't serve embeddings. E.g. `ollama/nomic-embed-text:latest`.
- Update the comment line above each entry (e.g. `# Local model - Phi 4 Mini (3.8B)`)
- Do **not** change `api_base` or `api_key` references
- **Out of scope:** entries that are not produced by the task, e.g. `ollama-mac-mistral` (a remote Mac's Ollama via `REMOTE_OLLAMA_API_BASE`). Leave these untouched.

## Step 3: Update the files

Edit `docker/ai/litellm/config/config.yaml` and `Taskfile.yaml` with the **Edit tool**, making targeted, minimal changes — one edit per model entry added/removed/renamed. Do **not** rewrite either file wholesale (a full-file rewrite risks silently dropping comments, provider groupings, or the inline doc links).

Also update `router_settings.fallbacks` in `config.yaml`:
- Reflect any **renamed** model names, and
- **Remove** any fallback entry that points to a model you removed in Step 2, so no fallback references a model that no longer exists in the config.

## Step 4: Verify

1. Lint the changed files: `pre-commit run --files docker/ai/litellm/config/config.yaml Taskfile.yaml` and fix any issues (the repo lints YAML with yamllint).
2. Restart LiteLLM so it re-reads and **parses** the new config, then confirm it came up cleanly (a YAML or unknown-model error surfaces here, not from re-reading the file):
   ```bash
   scripts/labctl.py service restart ai/litellm
   docker logs litellm --tail 50 2>&1 | grep -i "error\|invalid\|traceback" || echo "no startup errors"
   ```
3. Confirm the running container sees the intended config:
   ```bash
   docker exec litellm cat /app/config.yaml
   ```

## LiteLLM model ID format reference

| Provider               | LiteLLM format                     |
| ---------------------- | ---------------------------------- |
| Anthropic (direct)     | `anthropic/<model-id>`             |
| OpenAI (direct)        | `openai/<model-id>`                |
| Google Gemini (direct) | `gemini/<model-id>`                |
| OpenRouter             | `openrouter/<provider>/<model-id>` |
| Ollama (local, chat)   | `ollama_chat/<model-name>`         |
| Ollama (local, embed)  | `ollama/<model-name>:latest`       |

Example: `openrouter/meta-llama/llama-4-maverick`, `anthropic/claude-sonnet-4-6`

## Summary output

After completing the update, show a table of what changed:

| Model | Old ID | New ID | Action                   |
| ----- | ------ | ------ | ------------------------ |
| ...   | ...    | ...    | Added / Removed / Kept   |
