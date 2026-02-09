# Leitir - Iceland Library Loans

<img src="images/icon.png" alt="Leitir Logo" width="128" align="right">

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate with HACS](https://github.com/axelpaul/leitir-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/axelpaul/leitir-ha/actions/workflows/validate.yml)
[![Validate with hassfest](https://github.com/axelpaul/leitir-ha/actions/workflows/hassfest.yml/badge.svg)](https://github.com/axelpaul/leitir-ha/actions/workflows/hassfest.yml)

Home Assistant integration for [Leitir](https://leitir.is), Iceland's public library system. Track your library loans, see due dates, and renew books directly from Home Assistant.

<p align="center">
  <img src="images/screenshot.png" alt="Leitir Integration Screenshot" width="400">
</p>

## Features

- **Loan tracking**: See all your active library loans as sensors
- **Due date monitoring**: Get the next due date across all loans
- **Renewable count**: Know how many items can be renewed
- **Multi-account support**: Add multiple library accounts
- **Services**: Renew individual loans or all renewable items at once

## Sensors

| Sensor | Description |
|--------|-------------|
| `sensor.leitir_<account>_loans` | Total number of active loans (loan details in attributes) |
| `sensor.leitir_<account>_renewable` | Count of loans that can be renewed |
| `sensor.leitir_<account>_next_due` | Earliest due date among all loans |
| `sensor.leitir_<account>_loan_<title>` | Individual sensor per loan with details |

## Services

| Service | Description |
|---------|-------------|
| `leitir.renew_loan` | Renew a specific loan by ID |
| `leitir.renew_all` | Renew all renewable loans for an account |
| `leitir.refresh` | Force an immediate data refresh |

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the three dots in the top right corner
3. Select "Custom repositories"
4. Add `https://github.com/axelpaul/leitir-ha` with category "Integration"
5. Click "Install"
6. Restart Home Assistant

### Manual Installation

1. Download the latest release from GitHub
2. Copy the `custom_components/leitir` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** > **Devices & Services**
2. Click **Add Integration**
3. Search for "Leitir"
4. Enter your Leitir credentials:
   - **Account name**: A friendly name for this account
   - **Username**: Your Leitir username
   - **Password**: Your Leitir password
5. Click **Submit**

### Options

After setup, you can configure refresh times:

1. Go to the Leitir integration
2. Click **Configure**
3. Set custom refresh times (comma-separated, e.g., `08:00, 18:00`)

By default, the integration refreshes at 18:00 daily.

## Automation Examples

### Notify when a book is due soon

```yaml
automation:
  - alias: "Library book due reminder"
    trigger:
      - platform: template
        value_template: >
          {{ (as_timestamp(states('sensor.leitir_myaccount_next_due')) - as_timestamp(now())) < 86400 }}
    action:
      - service: notify.mobile_app
        data:
          title: "Library Reminder"
          message: "You have a book due tomorrow!"
```

### Auto-renew all books

```yaml
automation:
  - alias: "Auto renew library books"
    trigger:
      - platform: time
        at: "09:00:00"
    condition:
      - condition: numeric_state
        entity_id: sensor.leitir_myaccount_renewable
        above: 0
    action:
      - service: leitir.renew_all
        data:
          entry_id: "{{ config_entry_id('sensor.leitir_myaccount_loans') }}"
```

## Dashboard Example

A complete Lovelace dashboard example is available in [`examples/dashboard.yaml`](examples/dashboard.yaml). It includes:

- Summary cards showing total loans, books vs games, renewable count, due soon, and overdue items
- Quick action buttons for renewing all loans and refreshing data
- Auto-generated loan list sorted by due date with color-coded status indicators

**Required custom cards** (available via HACS):
- [layout-card](https://github.com/thomasloven/lovelace-layout-card)
- [mushroom](https://github.com/piitaya/lovelace-mushroom)
- [button-card](https://github.com/custom-cards/button-card)
- [auto-entities](https://github.com/thomasloven/lovelace-auto-entities)

## Support

If you encounter issues, please [open an issue](https://github.com/axelpaul/leitir-ha/issues) on GitHub.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

