# Ebook

## Customize Kobo Libra 2

### Install NickelMenu

> NickelMenu adds custom menu items to various menus in Kobo's eReader software. It works on all recent firmware versions, and persists between firmware upgrades. There are many built-in actions for controlling Nickel and for running external software.

Follow the instructions on https://pgaskin.net/NickelMenu/:

1. Connect your Kobo eReader to your computer over USB.
2. Download [KoboRoot.tgz](https://github.com/pgaskin/NickelMenu/releases) into `KOBOeReader/.kobo`. You may need to show hidden files to see the folder.
3. Safely eject your eReader and wait for it to reboot.
4. Ensure there is a new menu item in the top-left main menu entitled **NickelMenu** (it will appear in the bottom-right on firmware 4.23.15505+).
5. Connect you Kobo eReader to your computer again and create a new file (of any type) named `KOBOeReader/.adds/nm/config`, and follow the instructions in KOBOeReader/.adds/nm/doc to configure NickelMenu.

### Install KOreader

## Calibre-Web - Kobo Integration

https://github.com/janeczku/calibre-web/wiki/Kobo-Integration

Basic configuration >> Feature Configuration page
- Enable Kobo sync checkbox: ON
- Server External Port (for port forwarded API calls): 443
- Click "Save"

You can see latest device logs fromall apps in Settings - Logs or more specific app logs using the command line in SSH terminal

The Kobo eReader.conf file found under the .kobo/Kobo directory on Kobo devices is used to configure which URL the device uses for syncing books. By default, the config file contains the following row:

`api_endpoint=https://storeapi.kobo.com`

If the row does not exist it must be created under the [OneStoreServices] group.

Users can generate a URL to sync with Calibre-Web instead by clicking the Create/View button under their Calibre-Web profile page.
