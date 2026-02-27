---
description: Update LiteLLM config/config.yaml to use the latest model versions from each provider
---

Update the LiteLLM model configuration to use the latest available model IDs, removing outdated versions.

## Config file location

Read the current config via:
```bash
docker exec litellm cat /app/config.yaml
```

The source file is at `docker/ai/litellm/config/config.yaml`.

## Step 1: Look up latest models per provider (run searches in parallel)

Search the web for the current model IDs for each provider present in the config:

- **Anthropic**: Search "Anthropic Claude latest models API model IDs" → check https://docs.anthropic.com/en/docs/about-claude/models/overview
- **OpenAI**: Search "OpenAI latest models API model IDs" → check https://platform.openai.com/docs/models
- **Google Gemini**: Search "Google Gemini latest models API model IDs" → check https://ai.google.dev/gemini-api/docs/models
- **OpenRouter (Meta Llama)**: Search "Meta Llama latest models openrouter model IDs"
- **OpenRouter (DeepSeek)**: Search "DeepSeek latest models openrouter model IDs"
- **OpenRouter (xAI Grok)**: Search "xAI Grok latest models openrouter model IDs"

For each provider, identify:
1. The **latest stable** model ID (not preview/experimental unless that's the only option)
2. Whether the currently configured model has been **superseded** by a newer release
3. The **exact API model ID string** to use in LiteLLM params

## Step 2: Determine what to change

For each model in the config, decide:
- **Update**: A newer stable version exists → update the `model_name` key and `litellm_params.model` value
- **Keep**: Still the latest stable model → no change needed
- **Remove**: Superseded by a newer model already listed in the same config (avoid duplicates)

Preserve without changes:
- Local Ollama models (`ollama_chat/...`) — these are managed separately
- The overall YAML structure, comments, and provider groupings
- `api_key` and `api_base` references

## Step 3: Update the file

Write the updated config using:
```bash
tee "$(git rev-parse --show-toplevel)/docker/ai/litellm/config/config.yaml" > /dev/null << 'EOF'
<updated content>
EOF
```

Also update `router_settings.fallbacks` to reflect any renamed models.

## Step 4: Verify

Confirm the file was written correctly:
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
| ...   | ...    | ...    | Updated / Removed / Kept |
