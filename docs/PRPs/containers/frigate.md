## Base information for Frigate application

Application name: Frigate
Homepage: https://frigate.video
GitHub page: https://github.com/blakeblackshear/frigate
Install instructions URL: https://docs.frigate.video/frigate/installation#docker
Category: security
Dashboard Icon: frigate.png
Dashboard Group: Security
Short description: AI-powered local NVR with object detection for IP cameras
Long description: Frigate is a local NVR (network video recorder) system built for Home Assistant that uses AI-powered object detection on IP cameras. It minimizes resource use and maximizes performance by only looking for objects when and where necessary, performing real-time detection locally using OpenCV and TensorFlow.

## Container deployment

### Recommended Installation Method

Docker with Docker Compose is the **recommended** installation approach for Frigate. The container runs best on bare metal Debian-based systems with low-overhead hardware access for accelerators.

### Docker Compose Configuration

```yaml
services:
  frigate:
    container_name: frigate
    privileged: true
    restart: unless-stopped
    stop_grace_period: 30s
    image: ghcr.io/blakeblackshear/frigate:stable
    shm_size: "512mb"
    devices:
      - /dev/bus/usb:/dev/bus/usb  # For USB Coral devices
      - /dev/apex_0:/dev/apex_0    # For PCIe Coral devices
      - /dev/video11:/dev/video11  # For hardware acceleration (adjust as needed)
      - /dev/dri/renderD128:/dev/dri/renderD128  # For Intel/AMD hardware acceleration
    volumes:
      - /etc/localtime:/etc/localtime:ro
      - /path/to/your/config:/config
      - /path/to/your/storage:/media/frigate
      - type: tmpfs
        target: /tmp/cache
        tmpfs:
          size: 1000000000
    ports:
      - "8971:8971"  # Authenticated UI/API (without TLS)
      - "8554:8554"  # RTSP restreaming
      - "8555:8555/tcp"  # WebRTC connections
      - "8555:8555/udp"  # WebRTC connections
    environment:
      FRIGATE_RTSP_PASSWORD: "password"
```

### Storage Requirements

Frigate requires several volume mappings:

- **`/config`**: Configuration files and SQLite database
- **`/media/frigate/clips`**: Snapshot storage
- **`/media/frigate/recordings`**: Recording segments
- **`/media/frigate/exports`**: Exported clips and timelapses
- **`/tmp/cache`**: Temporary recording cache (strongly recommend tmpfs mount for performance)

### Shared Memory (shm-size) Requirements

The default Docker shm-size is 64MB, but Frigate needs more. Calculate using:

```
width × height × 1.5 × 20 + 270480 bytes, plus 40MB for logs
```

**Example**: Eight cameras at 1280×720 resolution requires approximately **253MB**.

For most setups, **512MB** is a safe starting point.

### Docker Image Tags

- `stable` – Standard amd64 build; RPi-optimized arm64 build (recommended for most users)
- `stable-standard-arm64` – Standard arm64 build (for non-RPi ARM systems)
- `stable-tensorrt` – Nvidia GPU-specific amd64 build
- `stable-rocm` – AMD GPU build

Community-supported tags:
- `stable-tensorrt-jp6` – Jetson platforms
- `stable-rk` – Rockchip platforms

### Port Mappings

| Port | Purpose |
|------|---------|
| 8971 | Authenticated UI/API (without TLS) |
| 5000 | Internal unauthenticated access (do not expose externally) |
| 8554 | RTSP restreaming |
| 8555 | WebRTC connections (TCP and UDP) |

### Hardware Acceleration Setup

#### Device Mappings

The devices you need to map depend on your hardware:

- **USB Coral**: `/dev/bus/usb:/dev/bus/usb`
- **PCIe Coral**: `/dev/apex_0:/dev/apex_0`
- **Intel Quick Sync**: `/dev/dri/renderD128:/dev/dri/renderD128`
- **AMD VAAPI**: `/dev/dri/renderD128:/dev/dri/renderD128`
- **Hailo-8**: `/dev/hailo0:/dev/hailo0` (requires driver installation)

For systems without hardware acceleration, remove the device mappings entirely.

#### Special Platform Notes

**Raspberry Pi**:
- Set `gpu_mem` to at least 128MB in `/boot/config.txt`
- Use external powered USB hub for Coral devices
- Ensure adequate power supply (official RPi power adapter recommended)

**Rockchip Systems**:
- Use `stable-rk` image tag
- Add device permissions: `/dev/dri`, `/dev/dma_heap`, `/dev/rga`, `/dev/mpp_service`

**Hailo-8**:
- Install Hailo driver before deploying container
- Map `/dev/hailo0` device

### Security Considerations

1. **Privileged Mode**: The compose example uses `privileged: true` for device access. For better security:
   - Use specific device mappings instead of privileged mode when possible
   - Add only required capabilities with `cap_add`
   - Run with user namespaces if your setup allows

2. **RTSP Password**: Change `FRIGATE_RTSP_PASSWORD` from default immediately

3. **Network Exposure**:
   - Port 5000 should NEVER be exposed externally (internal unauthenticated access)
   - Use reverse proxy with authentication for external access to port 8971
   - Consider TLS termination at reverse proxy

4. **File Permissions**: Ensure storage directories have appropriate ownership for container user

### Configuration File

Frigate requires a `config.yml` file in the `/config` directory. Minimal example:

```yaml
mqtt:
  enabled: False

cameras:
  dummy_camera:
    enabled: False
    ffmpeg:
      inputs:
        - path: rtsp://127.0.0.1:554/rtsp
          roles:
            - detect
```

See https://docs.frigate.video/configuration/ for full configuration reference.

### Improvements and Optimization

1. **Use tmpfs for cache**: The example uses tmpfs for `/tmp/cache` - this significantly improves performance by keeping temporary recordings in RAM

2. **Adjust shm-size**: Calculate exact requirements based on your camera count and resolution

3. **Hardware acceleration**: Always use hardware acceleration when available (GPU, Coral TPU) to reduce CPU usage

4. **Recording retention**: Configure retention policies in `config.yml` to manage storage usage

5. **Motion detection zones**: Define zones in configuration to reduce false positives and CPU usage

6. **Integration**: Consider integrating with Home Assistant for enhanced automation and UI

### Alternative: Docker Run Command

For non-Compose deployments:

```bash
docker run -d \
  --name frigate \
  --restart=unless-stopped \
  --stop-timeout 30 \
  --mount type=tmpfs,target=/tmp/cache,tmpfs-size=1000000000 \
  --device /dev/bus/usb:/dev/bus/usb \
  --device /dev/dri/renderD128 \
  --shm-size=512m \
  -v /path/to/your/storage:/media/frigate \
  -v /path/to/your/config:/config \
  -v /etc/localtime:/etc/localtime:ro \
  -e FRIGATE_RTSP_PASSWORD='your-secure-password' \
  -p 8971:8971 \
  -p 8554:8554 \
  -p 8555:8555/tcp \
  -p 8555:8555/udp \
  ghcr.io/blakeblackshear/frigate:stable
```

### Initial Setup Steps

1. Create required directories for config and storage
2. Create minimal `config.yml` in config directory
3. Adjust device mappings based on available hardware
4. Calculate and set appropriate shm-size
5. Set secure RTSP password
6. Deploy container
7. Access UI at `http://<host-ip>:8971`
8. Configure cameras and detection settings through UI or config file
