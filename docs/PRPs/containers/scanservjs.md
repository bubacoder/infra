## Base information for Scanservjs application

Application name: Scanservjs
Homepage: https://github.com/sbs20/scanservjs
GitHub page: https://github.com/sbs20/scanservjs
Install instructions URL: https://github.com/sbs20/scanservjs/blob/master/README.md
Category: tools
Dashboard Icon: scanservjs.png
Dashboard Group: Tools
Short description: Web UI for SANE document scanners
Long description: A responsive web UI for SANE document scanners that allows sharing scanners on a network without drivers or complicated installation. Supports various formats, filters and multipage scanning.

## Container deployment

### Docker Compose setup

Here's a Docker Compose configuration for Scanservjs:

```yaml
version: "3"
services:
  scanservjs:
    container_name: scanservjs
    image: sbs20/scanservjs:latest
    ports:
      - 8080:8080
    volumes:
      - /var/run/dbus:/var/run/dbus
      - ./config:/etc/scanservjs
      - ./output:/var/lib/scanservjs/output
    restart: unless-stopped
    privileged: true # Required for scanner access
```

### Configuration Options

The container accepts several environment variables to configure scanner detection and operation:

- `SANED_NET_HOSTS`: Semicolon-separated list of IP addresses for network SANE scanners
- `AIRSCAN_DEVICES`: Configuration for eSCL/AirScan scanners
- `PIXMA_HOSTS`: Semicolon-separated list of IPs for PIXMA scanners using bjnp protocol
- `DELIMITER`: Alternative delimiter if you need to include semicolons in environment variables
- `DEVICES`: Force add specific devices (semicolon delimited)
- `SCANIMAGE_LIST_IGNORE`: Set to `true` to force ignore `scanimage -L`
- `OCR_LANG`: Set OCR language (default is English)

### Volume Mapping

Two main volumes can be mapped:
- `/var/lib/scanservjs/output`: Directory where scanned images are stored
- `/etc/scanservjs`: Directory for configuration overrides

### Network and USB Scanner Support

The application supports scanners via:

1. **Network scanners**: Best option with SANE over network
2. **USB-connected scanners**: Requires device passthrough
3. **Driverless network scanners**: Uses sane-airscan with dbus

### Security Considerations

- The container runs as root by default
- `--privileged` mode gives the container full root access to the host and should be used cautiously
- For better security, consider:
  - Using SANE over Network instead of directly connecting USB devices
  - Creating a custom build with specific UID/GID: `docker build --build-arg UID=1234 --build-arg GID=5678`
  - Using volume mapping for persistent storage with proper permissions

### Additional Information

- The application requires SANE, which is included in the container
- Supports all SANE-compatible devices
- Features include cropping, source selection, various output formats, filters, and multipage scanning
- OpenAPI documentation is available at `/api-docs` endpoint
