Eclipse Mosquitto is an open-source MQTT broker implementing versions 5.0, 3.1.1, and 3.1 of the MQTT protocol.
It is lightweight and suitable for devices from single board computers to full servers, providing publish/subscribe
messaging capabilities with support for TLS, WebSockets, and various authentication methods.

Links:
- Home: https://mosquitto.org/
- Source: https://github.com/eclipse/mosquitto
- Image: https://hub.docker.com/_/eclipse-mosquitto
- Configure Authentication: https://mosquitto.org/documentation/authentication-methods/

TODO: Consider enabling TLS/SSL certificates for secure connections on port 8883
TODO: Implement authentication with password file and ACL for access control
TODO: Configure performance tuning for high-throughput environments (max_connections, max_queued_messages)
