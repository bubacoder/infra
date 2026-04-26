---
description: Update AI model configurations to use the latest model versions from each provider
---

Update the AI model configurations to use the latest available model IDs, removing outdated versions. This includes the LiteLLM config, the Ollama pull script, and syncing LiteLLM's local Ollama entries.

## Config file locations

Read the current LiteLLM config via:
```bash
docker exec litellm cat /app/config.yaml
```

Source files:
- `docker/ai/litellm/config/config.yaml` — LiteLLM model list
- `scripts/get-offline-data-ollama.sh` — Ollama model pull script

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

Example: config has Opus 4.5 and 4.6 → Opus 4.7 released → add 4.7, keep 4.6, remove 4.5.

Preserve without changes:
- The overall YAML structure, comments, and provider groupings
- `api_key` and `api_base` references

### Ollama local models (`scripts/get-offline-data-ollama.sh`)

The script must always include exactly:
- **One model ≤3B** — best benchmark performer in this size class (e.g. `phi4-mini`)
- **One model ≤8B** — best benchmark performer in this size class (e.g. `qwen3:8b`)
- **Embedding models** — keep as-is unless a clearly better alternative exists

Update both the pull tags and the inline comments with model size.

### LiteLLM Ollama entries sync

After updating `get-offline-data-ollama.sh`, update the `ollama-local-*` entries in `config.yaml` to match:
- `ollama_chat/<model>` must reflect the exact tag used in the pull script
- Update the comment line above each entry (e.g. `# Local model - Phi 4 Mini (3.8B)`)
- Do **not** change `api_base` or `api_key` references

## Step 3: Update the files

Write the updated LiteLLM config using:
```bash
tee "$(git rev-parse --show-toplevel)/docker/ai/litellm/config/config.yaml" > /dev/null << 'EOF'
<updated content>
EOF
```

Write the updated Ollama script using:
```bash
tee "$(git rev-parse --show-toplevel)/scripts/get-offline-data-ollama.sh" > /dev/null << 'EOF'
<updated content>
EOF
```

Also update `router_settings.fallbacks` in `config.yaml` to reflect any renamed models.

## Step 4: Verify

Confirm the LiteLLM config was written correctly:
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
| Ollama (local)         | `ollama_chat/<model-name>`         |

Example: `openrouter/meta-llama/llama-4-maverick`, `anthropic/claude-sonnet-4-6`

## Summary output

After completing the update, show a table of what changed:

| Model | Old ID | New ID | Action                   |
| ----- | ------ | ------ | ------------------------ |
| ...   | ...    | ...    | Added / Removed / Kept   |
