# OpenCloud for Home Assistant

[![Validate](https://github.com/d.shmt/ha-opencloud-integration/actions/workflows/validate.yml/badge.svg)](https://github.com/d.shmt/ha-opencloud-integration/actions/workflows/validate.yml)

A custom integration for **Home Assistant** to monitor your **OpenCloud** instance and storage spaces (drives) via the OpenCloud Graph API (`/graph/v1.0/me/drives`).

## Features (v1)

- **UI Configuration (`config_flow`)** with support for German and English
- **Re-authentication & Options Flow** (configurable update interval & SSL verification)
- **Server Device**:
  - `binary_sensor`: Server connectivity status (`Online` / `Offline`)
  - `sensor`: Number of Spaces / Drives
  - `sensor`: OpenCloud version (diagnostic, if exposed by server)
- **Per-Space / Drive Devices** (Personal, Project Spaces, Shares):
  - Used space (`DATA_SIZE`, GiB)
  - Free space (`DATA_SIZE`, GiB)
  - Total quota (`DATA_SIZE`, GiB, when quota is limited)
  - Usage percentage (`%`)
  - Quota status (`normal`, `nearing`, `critical`, `exceeded`)

## Installation

### Home Assistant Marketplace (Recommended)

1. Open **Settings → Marketplace** in Home Assistant.
2. Add `https://github.com/d.shmt/ha-opencloud-integration` as a custom repository (Category: **Integration**).
3. Install **OpenCloud** and restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration** and search for **OpenCloud**.

### Manual Installation

Copy the `custom_components/opencloud` folder into your Home Assistant `<config>/custom_components/` directory and restart Home Assistant.

## OpenCloud Authentication Setup

OpenCloud uses **OIDC** for browser logins, which issues short-lived tokens. For a background integration like Home Assistant, **App Tokens (`auth-app`)** are recommended:

1. Ensure `auth-app` is enabled in your OpenCloud LXC configuration:
   ```env
   PROXY_ENABLE_APP_AUTH=true
   OCIS_ADD_RUN_SERVICES=auth-app
   ```
2. Generate an App Token in OpenCloud (or via CLI inside your LXC):
   ```bash
   opencloud auth-app create --user-name=<username> --expiration=8760h
   ```
3. In Home Assistant, select **Username & App Token / Password (Basic Auth)** and enter your username and the generated App Token.

*(Alternatively, you can choose **Bearer Token** if you want to supply an API/OIDC token directly.)*
