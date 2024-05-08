# AI

## Tutorials

[A Guide to Quantization in LLMs](https://symbl.ai/developers/blog/a-guide-to-quantization-in-llms/)


## Local inference

### Hardware requirements

- CPU and GPU mode is supported
- You should have at least 8 GB of RAM available to run the 7B models, 16 GB to run the 13B models, and 32 GB to run the 33B models.
- On Apple M1 and higher Ollama performs great with 7B models due to the [Unified memory architecture](https://en.wikipedia.org/wiki/Apple_M1#Memory)
- High memory bandwidth (tipically GPU) is the top priority to achieve good performance

HW performance benchmarks:
- [Performance of llama.cpp on Apple Silicon M-series](https://github.com/ggerganov/llama.cpp/discussions/4167)
- [Multiple NVIDIA GPUs or Apple Silicon for Large Language Model Inference](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference)
- [Comparing Throughput Performance of Running Local LLMs and VLM on different systems](https://medium.com/aidatatools/comparing-throughput-performance-of-running-local-llms-and-vlm-on-different-systems-ca4ca82c8edc)

### Which model to choose?

-> See [models](models.md)


## AI LLM frameworks

> fabric is an open-source framework for augmenting humans using AI. It provides a modular framework for solving specific problems using a crowdsourced set of AI prompts that can be used anywhere.

https://github.com/danielmiessler/fabric

## LM Studio

https://lmstudio.ai/

## Text - Speech

Zero-Shot Speech Editing and Text-to-Speech in the Wild
https://github.com/jasonppy/VoiceCraft

## OpenAI parameters

- Temperature: Controls randomness. Lowering the temperature means that the model produces more repetitive and deterministic responses. Increasing the temperature results in more unexpected or creative responses. Try adjusting temperature or Top P but not both.
- Max length (tokens): Set a limit on the number of tokens per model response. The API supports a maximum of 4000 tokens shared between the prompt (including system message, examples, message history, and user query) and the model's response. One token is roughly four characters for typical English text.
- Stop sequences: Make responses stop at a desired point, such as the end of a sentence or list. Specify up to four sequences where the model will stop generating further tokens in a response. The returned text won't contain the stop sequence.
- Top probabilities (Top P): Similar to temperature, this controls randomness but uses a different method. Lowering Top P narrows the model’s token selection to likelier tokens. Increasing Top P lets the model choose from tokens with both high and low likelihood. Try adjusting temperature or Top P but not both.
- Frequency penalty: Reduce the chance of repeating a token proportionally based on how often it has appeared in the text so far. This decreases the likelihood of repeating the exact same text in a response.
- Presence penalty: Reduce the chance of repeating any token that has appeared in the text at all so far. This increases the likelihood of introducing new topics in a response.
- Pre-response text: Insert text after the user’s input and before the model’s response. This can help prepare the model for a response.
- Post-response text: Insert text after the model’s generated response to encourage further user input, as when modeling a conversation.

Source: https://learn.microsoft.com/en-us/training/modules/get-started-openai/7-use-azure-openai-playground

Ollama parameters: https://github.com/ollama/ollama/blob/main/docs/modelfile.md#valid-parameters-and-values

## Development

### JSON data output

- [Instructor](https://github.com/jxnl/instructor) - structured outputs for llms
- [Outlines](https://github.com/outlines-dev/outlines) - Structured Text Generation
- [awesome-llm-json](https://github.com/imaurer/awesome-llm-json) - Resource list for generating JSON using LLMs via function calling, tools, CFG. Libraries, Models, Notebooks, etc.

### RAG - Retrival Augmented Generation

https://www.llamaindex.ai/
