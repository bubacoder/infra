Kasm Workspaces is a docker container streaming platform for delivering browser-based access to desktops,
applications, and web services. Kasm uses devops-enabled Containerized Desktop Infrastructure (CDI) to
create on-demand, disposable, docker containers that are accessible via web browser.
Example use-cases include Remote Browser Isolation (RBI), Data Loss Prevention (DLP), Desktop as a Service (DaaS),
Secure Remote Access Services (RAS), and Open Source Intelligence (OSINT) collections.

**Application Setup**  
Access the installation wizard at https://kasm-install.${MYDOMAIN} and follow the instructions there.
Once setup is complete access https://kasm.${MYDOMAIN} and login with the credentials you entered during setup.

Default users:
- admin@kasm.local
- user@kasm.local

To add a persistent profile path to a Workspace:
- From the administrator menu first click on Workspaces -> Workspaces and edit your desired Workspace:
- Set "Persistent Profile Path" to `/profiles/{image_id}/{user_id}`
Details: https://kasmweb.com/docs/latest/guide/persistent_data/persistent_profiles.html#adding-a-persistent-profile-to-a-workspace

Kasm Workspaces can be configured to connect to fixed remote endpoints that are using either the Remote Desktop Protocol, VNC or SSH.  
Details: https://kasmweb.com/docs/latest/how_to/fixed_infrastructure.html

Links:
- Home: https://www.kasmweb.com/
- Image: https://docs.linuxserver.io/images/docker-kasm/
