Get up and running with Llama 3.2, Mistral, Gemma 2, and other large language models.

## GPU override for Ollama — AMD iGPU inference via the Vulkan backend

Enable by setting `GPU_COMPOSE_SUFFIX=amdgpu` in `config/docker/<hostname>/.env`.
The override reuses the shared host `GPU_RENDER_GID` and `GPU_VIDEO_GID` settings
defined in `config-example/docker/myhost/.env`.
Verify these once per host; no service-specific copies are needed.

NOTE: deliberately the STANDARD image, not :rocm — colony's Vega iGPU
(Ryzen 7 5825U, gfx90c) has no rocblas kernels in ROCm builds ("dropping
ROCm device"), while the standard image ships the ggml Vulkan backend
(the :rocm image does not), which supports Vega iGPUs via RADV.
OLLAMA_IGPU_ENABLE opts the iGPU into scheduling on Linux.

## References

- Home: [Ollama](https://ollama.com/)
- Source: [GitHub - ollama/ollama: Get up and running with Kimi, GLM, MiniMax, DeepSeek, gpt-oss, Qwen, Gemma and other models.](https://github.com/ollama/ollama)
- Vulkan backend for AMD/Intel GPUs: [Add Vulkan GPU Backend for AMD/Intel Support · Issue #11247 · ollama/ollama](https://github.com/ollama/ollama/issues/11247)
- Hardware support matrix (Vulkan path for iGPUs): [Hardware support - Ollama](https://docs.ollama.com/gpu)
