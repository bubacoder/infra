## Base information for ESPHome Device Builder application

Application name: ESPHome Device Builder
Homepage: https://esphome.io
GitHub page: https://github.com/esphome/esphome
Install instructions URL: https://esphome.io/guides/getting_started_command_line/#bonus-esphome-device-builder
Container image(s): esphome/esphome:2025.11.0-dev20251010
Category: automation
Dashboard Icon: esphome.png
Dashboard Group: Automation
Short description: Firmware builder for ESP8266/ESP32 IoT devices
Long description: ESPHome Device Builder is a tool for creating custom firmware for ESP8266/ESP32 microcontrollers through simple YAML configuration files and managing them through Home Automation systems like Home Assistant.

## Container deployment

### Docker Compose Example

```yaml
version: '3'
services:
  esphome:
    container_name: esphome
    image: esphome/esphome:2025.11.0-dev20251010
    volumes:
      - ./config:/config
      - /etc/localtime:/etc/localtime:ro
    ports:
      - "6052:6052"
    restart: unless-stopped
    network_mode: host  # Required for device discovery
    privileged: true    # Required for USB device access
    # For USB device passthrough:
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0  # Adjust based on your device
```

### Environment Variables

Optional environment variables that can be configured:

- `ESPHOME_DASHBOARD_USE_PING=true` - Use ping for device status
- `ESPHOME_DASHBOARD_RELATIVE_URL=/esphome` - If behind reverse proxy
- `USERNAME=admin` - Dashboard username (for authentication)
- `PASSWORD=your_password` - Dashboard password (for authentication)

### Volumes

- `/config` - Main configuration directory where YAML device configurations are stored
- `/etc/localtime` (optional) - For correct timezone

### Network Configuration

- Port `6052` - Web dashboard interface
- `network_mode: host` is recommended for mDNS device discovery
- Alternatively, use bridge mode with port mapping

### Security Considerations

1. **Authentication**: Configure dashboard authentication using USERNAME and PASSWORD environment variables when exposing the service to a network.

2. **USB Access**: The container requires privileged mode or specific device mappings to access USB devices for flashing.

3. **Network Access**: Consider restricting network access if not using mDNS discovery.

### Possible Improvements

1. **Version Pinning**: Pin to specific stable versions in production environments instead of development tags.

2. **Traefik Integration**: When using Traefik as a reverse proxy, add appropriate labels for automatic routing and TLS.

3. **Non-privileged Mode**: For improved security, consider configuring with specific device permissions rather than full privileged mode.

4. **USB Auto-discovery**: For more advanced setups, consider adding udev rules and device management to automatically detect ESP devices.

5. **Backup Strategy**: Implement regular backups of the configuration directory.
