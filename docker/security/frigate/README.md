Frigate is a local NVR (network video recorder) system built for Home Assistant
that uses AI-powered object detection on IP cameras. It minimizes resource use
and maximizes performance by only looking for objects when and where necessary,
performing real-time detection locally using OpenCV and TensorFlow.

TODO: Configure cameras and detection settings in config.yml
TODO: Adjust shm-size based on camera count and resolution (calculate: width × height × 1.5 × 20 + 270480 bytes + 40MB)
TODO: Consider integration with Home Assistant for enhanced automation
TODO: Configure motion detection zones to reduce false positives
TODO: Set up recording retention policies in config.yml

## GPU override for Frigate — AMD VAAPI video decode for camera streams

Enable by setting `GPU_COMPOSE_SUFFIX=amdgpu` in `config/docker/<hostname>/.env`.
The override reuses the shared host `GPU_RENDER_GID` and `GPU_VIDEO_GID` settings
defined in `config-example/docker/myhost/.env`.
Verify these once per host; no service-specific copies are needed.

Also set hwaccel in config/config.yml:
```yaml
ffmpeg:
  hwaccel_args: preset-vaapi
```

## References

- Home: [Frigate NVR](https://frigate.video)
- Source: [GitHub - blakeblackshear/frigate: NVR with realtime local object detection for IP cameras](https://github.com/blakeblackshear/frigate)
- Docs: [Introduction | Frigate](https://docs.frigate.video/)
- Install: [Installation | Frigate](https://docs.frigate.video/frigate/installation#docker)
- Config reference: https://docs.frigate.video/configuration/
