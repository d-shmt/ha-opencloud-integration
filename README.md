# OpenCloud for Home Assistant

[![Validate](https://github.com/d-shmt/ha-opencloud-integration/actions/workflows/validate.yml/badge.svg)](https://github.com/d-shmt/ha-opencloud-integration/actions/workflows/validate.yml)

A custom integration for **Home Assistant** to monitor your **OpenCloud** instance and storage spaces (drives) via the OpenCloud Graph API (`/graph/v1.0/me/drives`).

## Features

- **UI Configuration (`config_flow`)** in German and English
- **Two-Step Area & Drive Selection** (available during setup and via **Configure**):
  1. Choose which areas to include (**Personal**, **Spaces**, **Shares**)
  2. Refine which individual drives or spaces should be integrated
- **Re-authentication & Options Flow** (configurable update interval & SSL verification)
- **Server Device**:
  - `binary_sensor`: Server connectivity status (`Online` / `Offline`)
  - `sensor`: Number of integrated Spaces / Drives
  - `sensor`: OpenCloud version (diagnostic, if exposed by server)
- **Per-Space / Drive Devices**:
  - Used space (`DATA_SIZE`, GiB)
  - Free space (`DATA_SIZE`, GiB)
  - Total quota (`DATA_SIZE`, GiB, when quota is limited)
  - Usage percentage (`%`)
  - Quota status (`normal`, `nearing`, `critical`, `exceeded`)

## Installation

### Home Assistant Marketplace (Recommended)

1. Open **Settings → Marketplace** in Home Assistant.
2. Add `https://github.com/d-shmt/ha-opencloud-integration` as a custom repository (Category: **Integration**).
3. Install **OpenCloud** and restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration** and search for **OpenCloud**.

### Manual Installation

Copy the `custom_components/opencloud` folder into your Home Assistant `<config>/custom_components/` directory and restart Home Assistant.
