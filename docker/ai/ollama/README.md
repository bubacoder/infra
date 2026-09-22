Get up and running with Llama 3.2, Mistral, Gemma 2, and other large language models.

Links:
- Home: https://ollama.com/
- Source: https://github.com/ollama/ollama

GPU override for Ollama — AMD iGPU inference via the Vulkan backend.
Enable by setting GPU_COMPOSE_SUFFIX=amdgpu in config/docker/<hostname>/.env
NOTE: deliberately the STANDARD image, not :rocm — colony's Vega iGPU
(Ryzen 7 5825U, gfx90c) has no rocblas kernels in ROCm builds ("dropping
ROCm device"), while the standard image ships the ggml Vulkan backend
(the :rocm image does not), which supports Vega iGPUs via RADV.
OLLAMA_IGPU_ENABLE opts the iGPU into scheduling on Linux.
References:
- Vulkan backend for AMD/Intel GPUs: https://github.com/ollama/ollama/issues/11247
- Hardware support matrix (Vulkan path for iGPUs): https://docs.ollama.com/gpu
