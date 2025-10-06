## Base information for Eclipse Mosquitto application

Application name: Eclipse Mosquitto
Homepage: https://mosquitto.org/
GitHub page: https://github.com/eclipse/mosquitto
Install instructions URL: https://hub.docker.com/_/eclipse-mosquitto
Container image(s): eclipse-mosquitto:2.0.22-openssl
Category: automation
Dashboard Icon: https://mosquitto.org/favicon-16x16.png
Dashboard Group: Connections
Short description: Open-source MQTT broker implementing protocol versions 5.0, 3.1.1, and 3.1
Long description: Eclipse Mosquitto is an open-source MQTT broker implementing versions 5.0, 3.1.1, and 3.1 of the MQTT protocol. It is lightweight and suitable for devices from single board computers to full servers, providing publish/subscribe messaging capabilities with support for TLS, WebSockets, and various authentication methods.

## Container deployment

### Basic Docker Compose Configuration

The most common deployment uses three main ports and requires persistent storage for configuration, data, and logs:

```yaml
services:
  mosquitto:
    image: eclipse-mosquitto:2.0.22-openssl
    container_name: mosquitto
    restart: unless-stopped
    ports:
      - "1883:1883" # MQTT
      - "8883:8883" # MQTTS (secure)
      - "9001:9001" # WebSockets
    volumes:
      - ./mosquitto/config:/mosquitto/config
      - ./mosquitto/data:/mosquitto/data
      - ./mosquitto/log:/mosquitto/log
```

### Advanced Production Setup

For production environments, consider this enhanced configuration:

```yaml
version: '3.8'
networks:
  mqtt-net:
    driver: bridge

services:
  mosquitto:
    image: eclipse-mosquitto:2.0.22-openssl
    user: mosquitto
    volumes:
      - type: bind
        source: ./config/
        target: /mosquitto/config/
        read_only: false
      - type: bind
        source: ./log/
        target: /mosquitto/log/
        read_only: false
      - type: volume
        source: mosquitto-data
        target: /mosquitto/data/
    ports:
      - "1883:1883"  # Standard MQTT
      - "8883:8883"  # MQTT over TLS
      - "9001:9001"  # WebSockets
    networks:
      - mqtt-net
    restart: unless-stopped

volumes:
  mosquitto-data:
    name: "mosquitto-data"
```

### Configuration Setup

Before deployment, create the required configuration structure:

1. **Directory Structure**:
   ```
   ./mosquitto/
   ├── config/
   │   ├── mosquitto.conf
   │   └── passwd (if using authentication)
   ├── data/ (for persistence)
   └── log/ (for logging)
   ```

2. **Sample mosquitto.conf**:
   ```
   # Persistence settings
   persistence true
   persistence_location /mosquitto/data/

   # Logging settings
   log_dest file /mosquitto/log/mosquitto.log

   # Authentication settings (uncomment if needed)
   # allow_anonymous false
   # password_file /mosquitto/config/passwd

   # Default MQTT port
   listener 1883

   # WebSocket port (optional)
   listener 9001
   protocol websockets

   # TLS/SSL settings (uncomment and configure if needed)
   # listener 8883
   # cafile /mosquitto/config/ca.crt
   # certfile /mosquitto/config/server.crt
   # keyfile /mosquitto/config/server.key
   ```

### Environment Variables

Key environment variables for configuration:
- No specific environment variables are required, but configuration is done through the `mosquitto.conf` file and mounted volumes

### Security Considerations

1. **Authentication**: Enable password authentication by setting `allow_anonymous false` and creating a password file
2. **TLS/SSL**: Configure TLS certificates for secure connections on port 8883
3. **Access Control**: Use ACL (Access Control List) files to restrict topic access per user
4. **Firewall**: Ensure only necessary ports are exposed (1883, 8883, 9001)

### Authentication Setup

To add user authentication:

```bash
# Create password file and add first user
docker exec -it mosquitto mosquitto_passwd -c /mosquitto/config/passwd username1

# Add additional users (omit -c flag)
docker exec -it mosquitto mosquitto_passwd /mosquitto/config/passwd username2
```

### Testing the Deployment

Test the MQTT broker using the included client tools:

```bash
# Subscribe to a topic
docker exec -it mosquitto mosquitto_sub -t 'test/topic' -v

# Publish a message (in another terminal)
docker exec -it mosquitto mosquitto_pub -t 'test/topic' -m 'hello world'
```

### Performance Tuning

For high-throughput environments, consider:
- Adjusting `max_connections` in mosquitto.conf
- Configuring `max_queued_messages` for QoS handling
- Setting appropriate `message_size_limit`
- Using persistent sessions strategically
