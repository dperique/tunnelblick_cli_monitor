# Tunnelblick CLI Monitor

Automate your Tunnelblick VPN connection on macOS with support for two-factor authentication (password prefix + YubiKey token). No more manual reconnections when your VPN drops!

## Features

- **Automatic VPN connection** with password automation
- **Connection monitoring** with auto-reconnect capability
- **Secure credential storage** in macOS keychain
- **YubiKey/Token support** for two-factor authentication
- **CLI interface** for easy scripting and automation

## Quick Start

1. **Install dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

2. **List your VPN configurations:**
   ```bash
   ./tunnelblick-vpn list
   ```

3. **Connect to VPN (one-time manual connection):**
   ```bash
   ./tunnelblick-vpn connect "Red Hat Global VPN"
   ```

4. **Set up monitoring (one-time credential setup):**
   ```bash
   ./tunnelblick-monitor "Red Hat Global VPN" --setup
   ```

5. **Start auto-monitoring:**
   ```bash
   ./tunnelblick-monitor "Red Hat Global VPN"
   ```

## VPN Control

### List available VPN configurations:
```bash
./tunnelblick-vpn list
```

### Check VPN status:
```bash
./tunnelblick-vpn status "Red Hat Global VPN"
```

### Connect to VPN:
```bash
./tunnelblick-vpn connect "Red Hat Global VPN"
```

### Disconnect from VPN:
```bash
./tunnelblick-vpn disconnect "Red Hat Global VPN"
```

## VPN Monitoring

The monitor automatically detects VPN disconnections and handles reconnection. Perfect for avoiding those annoying timeouts during bathroom breaks!

### Setup credentials (one-time):
```bash
./tunnelblick-monitor "Red Hat Global VPN" --setup
```
This stores your password prefix securely in macOS keychain.

### Test stored credentials:
```bash
./tunnelblick-monitor "Red Hat Global VPN" --test
```

### Start monitoring:
```bash
./tunnelblick-monitor "Red Hat Global VPN"
```
Checks connection every 30 seconds and prompts for YubiKey token when reconnection is needed.

**Interactive feature:** Press Enter while monitoring to immediately check VPN status and reconnect if needed. No more waiting for the next check cycle!

### Custom check interval:
```bash
./tunnelblick-monitor "Red Hat Global VPN" --check-interval 60
```

## How Monitoring Works

1. **Detects VPN drops** automatically (every 30 seconds by default)
2. **Interactive checking:** Press Enter to immediately check VPN status
3. **Prompts for YubiKey token** when reconnection is needed
4. **Combines stored prefix + fresh token** for authentication
5. **Handles the entire reconnection process** automatically

**Semi-automatic:** You still need to provide fresh YubiKey tokens when prompted, but everything else is handled automatically.

**Perfect for laptop users:** When you come back to your laptop and see VPN is down, just press Enter to immediately trigger a reconnection instead of waiting for the next scheduled check!

## Security & Storage

### Credential Storage
- **Password prefix**: Stored securely in macOS keychain
- **YubiKey tokens**: Never stored (always prompted fresh)
- **Service name**: `tunnelblick_vpn_<VPN_Config_Name>`
- **Storage location**: Same keychain as Safari passwords, WiFi credentials, etc.

### View/Manage stored credentials:
```bash
open "/System/Library/CoreServices/Applications/Keychain Access.app"
```
Then search for "tunnelblick_vpn" to see your stored entries.

### Remove stored credentials:
```bash
python3 -c "import keyring; keyring.delete_password('tunnelblick_vpn_Red Hat Global VPN', 'prefix')"
```

## Requirements

- macOS with Tunnelblick installed
- Python 3.6+
- Terminal accessibility permissions (see Troubleshooting)

## Installation

1. **Clone this repository:**
   ```bash
   git clone https://github.com/dperique/tunnelblick_cli_monitor.git
   cd tunnelblick_cli_monitor
   ```

2. **Install dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Make scripts executable:**
   ```bash
   chmod +x *.py
   ```

## Troubleshooting

### AppleScript Permissions
If you get "AppleScript error" messages:

1. Go to **System Preferences → Security & Privacy → Privacy → Accessibility**
2. Add your terminal app (Terminal.app, iTerm2, etc.)
3. Make sure it's checked/enabled

### Common Issues

- **"No VPN configurations found"**: Make sure Tunnelblick is running and has VPN configs set up
- **Connection fails**: Double-check your password prefix and YubiKey token
- **Permission denied**: Run `chmod +x *.py` to make scripts executable

## Background Operation

### Run monitor in background:
```bash
nohup ./tunnelblick-monitor "Red Hat Global VPN" > vpn_monitor.log 2>&1 &
```

### Create aliases (add to your shell profile):
```bash
alias vpn-connect="./tunnelblick-vpn connect"
alias vpn-status="./tunnelblick-vpn status"
alias vpn-list="./tunnelblick-vpn list"
```

## Repository

**GitHub:** https://github.com/dperique/tunnelblick_cli_monitor

## License

MIT License - Feel free to use and modify as needed.