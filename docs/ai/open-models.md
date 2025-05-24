
# Open Source LLMs

This page discusses the open source (open weights) models which can be used with [Ollama](https://ollama.com/), [LM Studio](https://lmstudio.ai/) and similar tools. For proprietary, closed source models, see: [Online services](online-services.md)

Some Large Language Models are more optimized for generic chat, others are coding-oriented.

Model libraries:
- [Hugging Face](https://huggingface.co/)
- [Ollama - Model Library](https://ollama.com/library/)

Tools for limited GPU resources:
- [LLM RAM Calculator](https://llm-calc.rayfernando.ai/)
- [GPU-Poor LLM Arena](https://huggingface.co/spaces/k-mktr/gpu-poor-llm-arena) (models with maximum 14B parameters)

TODO: Update the list of best models

### Models for generic chat / instruct (=instruction following)

- [Mistral-7B-Instruct-v0.2](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.2)
- [Dolphin-Mistral](https://ollama.com/library/dolphin-mistral:latest) - The uncensored Dolphin model based on Mistral that excels at coding tasks. Fine-tune of Mistral
- [WizardLM-2](https://wizardlm.github.io/WizardLM2/) - Fine-tune of Mistral
- [Llama 3 by Meta](https://ai.meta.com/blog/meta-llama-3/) <-- Top
- [DBRX by Databricks](https://ollama.com/library/dbrx)

### Optimized for Coding

Note: As of 2025, general-purpose (proprietary) models are also excellent for coding. Check [Aider LLM Leaderboards](https://aider.chat/docs/leaderboards/).

- [Code Llama by Meta](https://ai.meta.com/blog/code-llama-large-language-model-coding/)
- [CodeGemma by Google](https://ai.google.dev/gemma/docs/codegemma)
- [DeepSeek-Coder-V2](https://huggingface.co/deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct) - [Ollama](https://ollama.com/library/deepseek-coder-v2)
- [Qwen2.5-Coder](https://qwenlm.github.io/blog/qwen2.5-coder/) (formerly known as CodeQwen) - context: 128K - [Ollama](https://ollama.com/library/qwen2.5-coder) <-- Top

### Optimized for long context / RAG

- [Command-R by Cohere](https://huggingface.co/CohereForAI/c4ai-command-r-v01) (also good for tool use)

### Optimized for JSON output / function calling / tool use

- [C4AI Command R+](https://huggingface.co/CohereForAI/c4ai-command-r-plus) (2024-03-20, CC-BY-NC, Cohere) is a 104B parameter multilingual model with advanced Retrieval Augmented Generation (RAG) and tool use capabilities, optimized for reasoning, summarization, and question answering across 10 languages. Supports quantization for efficient use and demonstrates unique multi-step tool integration for complex task execution.

- [Hermes 2 Pro - Mistral 7B](https://huggingface.co/NousResearch/Hermes-2-Pro-Mistral-7B) (2024-03-13, Nous Research) is a 7B parameter model that excels at function calling, JSON structured outputs, and general tasks. Trained on an updated OpenHermes 2.5 Dataset and a new function calling dataset, it uses a special system prompt and multi-turn structure. Achieves 91% on function calling and 84% on JSON mode evaluations.

- [Gorilla OpenFunctions v2](https://gorilla.cs.berkeley.edu//blogs/7_open_functions_v2.html) (2024-02-27, Apache 2.0 license, [Charlie Cheng-Jie Ji et al.](https://gorilla.cs.berkeley.edu//blogs/7_open_functions_v2.html))  interprets and executes functions based on JSON Schema Objects, supporting multiple languages and detecting function relevance.

- [NexusRaven-V2](https://nexusflow.ai/blogs/ravenv2) (2023-12-05, Nexusflow)  is a 13B model outperforming GPT-4 in zero-shot function calling by up to 7%, enabling effective use of software tools. Further instruction-tuned on CodeLlama-13B-instruct.

- [Functionary](https://functionary.meetkai.com/) (2023-08-04, [MeetKai](https://meetkai.com/)) interprets and executes functions based on JSON Schema Objects, supporting various compute requirements and call types. Compatible with OpenAI-python and llama-cpp-python for efficient function execution in JSON generation tasks.

Source: [awesome-llm-json](https://github.com/imaurer/awesome-llm-json?tab=readme-ov-file#local-models)

### Vision models (multimodal)

- [LLaVA](https://ollama.com/blog/vision-models) - [details](https://llava-vl.github.io/blog/2024-01-30-llava-next/)
- Llama 3.2 by Meta
- Pixtral 12B by Mistral - https://youtu.be/7aGTKJJMb5w
