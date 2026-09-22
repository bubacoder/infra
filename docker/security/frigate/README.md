Frigate is a local NVR (network video recorder) system built for Home Assistant
that uses AI-powered object detection on IP cameras. It minimizes resource use
and maximizes performance by only looking for objects when and where necessary,
performing real-time detection locally using OpenCV and TensorFlow.

Links:
- Home: [Frigate NVR](https://frigate.video)
- Source: [GitHub - blakeblackshear/frigate: NVR with realtime local object detection for IP cameras](https://github.com/blakeblackshear/frigate)
- Docs: [Introduction | Frigate](https://docs.frigate.video/)
- Install: [Installation | Frigate](https://docs.frigate.video/frigate/installation#docker)
- Config reference: https://docs.frigate.video/configuration/

GPU acceleration: set GPU_COMPOSE_SUFFIX=amdgpu in host .env to load frigate-amdgpu.yaml (VAAPI/AMD).

TODO: Configure cameras and detection settings in config.yml
TODO: Adjust shm-size based on camera count and resolution (calculate: width × height × 1.5 × 20 + 270480 bytes + 40MB)
TODO: Consider integration with Home Assistant for enhanced automation
TODO: Configure motion detection zones to reduce false positives
TODO: Set up recording retention policies in config.yml

GPU override for Frigate — AMD VAAPI video decode for camera streams.
Enable by setting GPU_COMPOSE_SUFFIX=amdgpu in config/docker/<hostname>/.env
Also set hwaccel in config/config.yml:
  ffmpeg:
    hwaccel_args: preset-vaapi
