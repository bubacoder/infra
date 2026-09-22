Crowdsec - An open-source, lightweight agent to detect and respond to bad behaviours.

Links:
- Home: [Curated Threat Intelligence Powered by the Crowd | CrowdSec](https://www.crowdsec.net/)
- Image: [crowdsecurity/crowdsec - Docker Image](https://hub.docker.com/r/crowdsecurity/crowdsec)
- Source: [GitHub - crowdsecurity/example-docker-compose: Example integration of crowdsec in docker-compose](https://github.com/crowdsecurity/example-docker-compose)
- Tutorial: https://docs.ibracorp.io/crowdsec/

Register to dashboard, subscribe to blocklists: [Safer Together - CrowdSec Console](https://app.crowdsec.net/)  
Configure iptables bouncer with Ansible: `ansible/roles/debian_base/tasks/45-crowdsec.yaml`

Useful commands - execute within the container like `docker exec crowdsec <command>`:
- `cscli collections list`
- `cscli bouncers list`
- `cscli decisions list`
- `cscli alerts list`
- `cscli metrics`
