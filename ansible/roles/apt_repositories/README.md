# Signed APT repositories and packages

This role configures opt-in third-party repositories on Debian/Ubuntu and installs
their packages. It uses `deb822_repository` with repository-scoped signing keys;
it does not add keys to APT's global trust store.

For administrative tools, set `debian_tools_apt_repositories` in host/group
inventory. The `debian_tools` role passes that list to this role:

```yaml
debian_tools_apt_repositories:
  - name: azure-cli
    uri: https://packages.microsoft.com/repos/azure-cli/
    suites: resolute
    components: [main]
    signing_key_url: https://packages.microsoft.com/keys/microsoft.asc
    packages: [azure-cli]
    enabled: true
```

Other roles can include `apt_repositories` directly and supply
`apt_repositories_items` using the same schema. Keep service configuration,
startup sequencing and package holds in the calling role.

## Configuration

| Field | Meaning |
| --- | --- |
| `name` | Unique repository/file name; letters, digits, `_` and `-` |
| `uri` | HTTPS APT repository URL |
| `suites` | Distribution suite or list of suites |
| `components` | Repository component or list of components |
| `signing_key_url` | HTTPS public signing-key URL |
| `packages` | Nonempty package list; `package=version` pins are supported |
| `enabled` | Defaults to `true`; `false` skips the entire entry |
| `architectures` | Optional APT architecture list, e.g. `[amd64, arm64]` |
| `package_state` | `present` (default) or `latest` |
| `allow_downgrade` | Defaults to `false`; explicitly enabled for Docker version pins |

An empty list does nothing. Disabled or removed entries do **not** remove
previously configured sources, keys or packages. This is an installation opt-in,
not an uninstall mechanism. Inventory list overrides replace the entire list.
Ensure repository names are unique across roles; the same name owns the same
`.sources` file.

Enabled entries install `ca-certificates` and `python3-debian`, configure the
signed repository, and refresh APT metadata before package installation. Metadata
is cached for one hour unless the repository definition changes.

## Azure CLI

The shared Debian inventory offers a reusable definition:

```yaml
debian_tools_apt_repositories:
  - "{{ debian_tools_apt_repository_catalog.azure_cli }}"
```

Enable it by adding that entry; disable installation by omitting it, setting the
list to `[]`, or overriding the entry with `enabled: false`. Azure CLI is no
longer a Homebrew package group. Migrate private inventory overrides using
`debian_tools_brew_install_groups.azure` to the new list.

Microsoft publishes `resolute` packages for Ubuntu 26.04 but no `trixie` suite.
The catalog uses Microsoft's documented `bookworm` fallback for Debian 13;
other releases use their distribution codename. Unsupported combinations fail
rather than silently selecting an arbitrary suite. See the
[Microsoft installation guide](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-linux?pivots=apt).

An existing Linuxbrew Azure CLI installation is not automatically removed. Check
`command -v az` for PATH shadowing when migrating an existing workstation.
On macOS Azure CLI belongs to `mac_base_brew_cask_packages`, not the formula list;
Homebrew's update migration handles the retired formula. Azure login data in
`~/.azure` is not managed by these roles.
