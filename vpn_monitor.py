#!/usr/bin/env python3

"""
VPN Connection Monitor and Auto-Reconnect

This script monitors your VPN connection and automatically reconnects when it drops.
It stores your credentials securely and can run in the background.

Examples:
    python3 vpn_monitor.py MyVPNConfig --check-interval 30
    python3 vpn_monitor.py MyVPNConfig --daemon
"""

import subprocess
import time
import getpass
import argparse
import signal
import sys
from pathlib import Path
import keyring
from typing import Optional


def _run_applescript(script: str) -> str:
    """
    Execute AppleScript and return the output.

    Arg(s):
        script (str): AppleScript code to execute
    Return Value(s):
        str: Output from the AppleScript execution
    """
    try:
        result = subprocess.run(['osascript', '-e', script],
                              capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"AppleScript error: {e.stderr}")
        return ""


def _get_vpn_status(config_name: str) -> str:
    """
    Get the connection status of a specific VPN configuration.

    Arg(s):
        config_name (str): Name of the VPN configuration
    Return Value(s):
        str: Status of the VPN connection (CONNECTED, EXITING, etc.)
    """
    script = '''
    tell application "Tunnelblick"
        get properties of configurations
    end tell
    '''

    result = _run_applescript(script)
    if not result:
        return "UNKNOWN"

    # Parse the properties string to find the status for our config
    # Format: autoconnect:NO, state:EXITING, bytesOut:0, name:home-vpn2, class:configuration, bytesIn:0, ...
    configs = result.split('class:configuration')
    for config_block in configs:
        if f'name:{config_name}' in config_block:
            # Extract state from this block
            state_start = config_block.find('state:')
            if state_start != -1:
                state_end = config_block.find(',', state_start)
                if state_end == -1:
                    state_end = len(config_block)
                return config_block[state_start + 6:state_end].strip()

    return "NOT_FOUND"


def _connect_vpn(config_name: str, password: str) -> bool:
    """
    Connect to VPN with the provided credentials.

    Arg(s):
        config_name (str): Name of the VPN configuration
        password (str): Complete password (prefix + token)
    Return Value(s):
        bool: True if connection was successful, False otherwise
    """
    # First, try to connect
    script = f'''
    tell application "Tunnelblick"
        connect "{config_name}"
    end tell
    '''

    _run_applescript(script)

    # Wait a moment for the password dialog to appear
    time.sleep(2)

    # Send the credentials using System Events
    password_script = f'''
    tell application "System Events"
        repeat 15 times
            try
                tell process "Tunnelblick"
                    if exists window "Tunnelblick: Login Required" then
                        tell window "Tunnelblick: Login Required"
                            if exists text field 2 then
                                set focused of text field 2 to true
                                set value of text field 2 to "{password}"
                                delay 0.2
                                if exists button "OK" then
                                    click button "OK"
                                    exit repeat
                                end if
                            end if
                        end tell
                    end if
                end tell
            on error
                -- Continue trying
            end try
            delay 0.7
        end repeat
    end tell
    '''

    _run_applescript(password_script)

    # Wait for connection to establish
    for i in range(30):  # Wait up to 30 seconds
        status = _get_vpn_status(config_name)
        if status == "CONNECTED":
            return True
        elif "EXITING" in status or "DISCONNECTED" in status:
            return False
        time.sleep(1)

    return False


def _store_credentials(config_name: str, prefix: str) -> None:
    """
    Store VPN credentials securely in the system keychain.

    Arg(s):
        config_name (str): Name of the VPN configuration
        prefix (str): Password prefix to store
    """
    service_name = f"tunnelblick_vpn_{config_name}"
    keyring.set_password(service_name, "prefix", prefix)
    print("✅ Credentials stored securely in keychain")


def _get_stored_credentials(config_name: str) -> Optional[str]:
    """
    Retrieve stored VPN credentials from the system keychain.

    Arg(s):
        config_name (str): Name of the VPN configuration
    Return Value(s):
        Optional[str]: Password prefix if found, None otherwise
    """
    service_name = f"tunnelblick_vpn_{config_name}"
    try:
        prefix = keyring.get_password(service_name, "prefix")
        return prefix
    except Exception:
        return None


def _check_internet_connectivity() -> bool:
    """
    Check if we have internet connectivity by pinging a reliable server.

    Return Value(s):
        bool: True if internet is accessible, False otherwise
    """
    try:
        result = subprocess.run(['ping', '-c', '1', '-W', '5000', '8.8.8.8'],
                              capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


class VPNMonitor:
    """
    VPN connection monitor that handles automatic reconnection.
    """

    def __init__(self, config_name: str, check_interval: int = 30):
        """
        Initialize the VPN monitor.

        Arg(s):
            config_name (str): Name of the VPN configuration to monitor
            check_interval (int): How often to check connection status (seconds)
        """
        self.config_name = config_name
        self.check_interval = check_interval
        self.running = False
        self.reconnect_count = 0

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame) -> None:
        """
        Handle shutdown signals gracefully.

        Arg(s):
            signum (int): Signal number
            frame: Stack frame (unused)
        """
        print(f"\nReceived signal {signum}. Shutting down VPN monitor...")
        self.running = False

    def _get_yubikey_token(self) -> str:
        """
        Prompt for YubiKey token with timeout.

        Return Value(s):
            str: 6-digit token from YubiKey
        """
        while True:
            token = input("YubiKey token (6 digits): ").strip()
            if token.isdigit() and len(token) == 6:
                return token
            print("Error: Token must be exactly 6 digits. Please try again.")

    def setup_credentials(self) -> bool:
        """
        Set up and store VPN credentials for monitoring.

        Return Value(s):
            bool: True if credentials were set up successfully, False otherwise
        """
        print(f"Setting up credentials for VPN: {self.config_name}")
        print("These will be stored securely in your system keychain.")

        prefix = getpass.getpass("Password prefix: ")
        if not prefix:
            print("Error: Password prefix cannot be empty")
            return False

        _store_credentials(self.config_name, prefix)
        return True

    def test_connection(self) -> bool:
        """
        Test VPN connection with stored credentials.

        Return Value(s):
            bool: True if test connection was successful, False otherwise
        """
        prefix = _get_stored_credentials(self.config_name)
        if not prefix:
            print("No stored credentials found. Please run setup first.")
            return False

        print("Testing connection with stored credentials...")
        token = self._get_yubikey_token()
        full_password = prefix + token

        return _connect_vpn(self.config_name, full_password)

    def start_monitoring(self) -> None:
        """
        Start monitoring the VPN connection and auto-reconnect when needed.
        """
        prefix = _get_stored_credentials(self.config_name)
        if not prefix:
            print("No stored credentials found. Please run setup first.")
            return

        print(f"Starting VPN monitor for '{self.config_name}'")
        print(f"Check interval: {self.check_interval} seconds")
        print("Press Ctrl+C to stop monitoring")

        self.running = True

        while self.running:
            try:
                status = _get_vpn_status(self.config_name)
                current_time = time.strftime("%Y-%m-%d %H:%M:%S")

                if status == "CONNECTED":
                    print(f"[{current_time}] VPN is connected ✅")
                    # Reset reconnect count on successful connection
                    self.reconnect_count = 0
                else:
                    print(f"[{current_time}] VPN is disconnected ({status}) ❌")

                    # Check if we have internet connectivity
                    if _check_internet_connectivity():
                        print("Internet connectivity detected. Attempting to reconnect...")
                        token = self._get_yubikey_token()
                        full_password = prefix + token

                        if _connect_vpn(self.config_name, full_password):
                            self.reconnect_count += 1
                            print(f"✅ Reconnected successfully (attempt #{self.reconnect_count})")
                        else:
                            print("❌ Reconnection failed. Will try again next cycle.")
                    else:
                        print("No internet connectivity. Waiting for network...")

                # Wait for next check
                if self.running:
                    time.sleep(self.check_interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error during monitoring: {e}")
                time.sleep(5)  # Wait a bit before retrying

        print("VPN monitoring stopped.")


def main() -> None:
    """
    Main function to handle command line arguments and start monitoring.
    """
    parser = argparse.ArgumentParser(description='VPN Connection Monitor and Auto-Reconnect')
    parser.add_argument('config_name', help='Name of the VPN configuration to monitor')
    parser.add_argument('--check-interval', '-i', type=int, default=30,
                       help='How often to check connection status in seconds (default: 30)')
    parser.add_argument('--setup', '-s', action='store_true',
                       help='Set up and store VPN credentials')
    parser.add_argument('--test', '-t', action='store_true',
                       help='Test connection with stored credentials')

    args = parser.parse_args()

    monitor = VPNMonitor(args.config_name, args.check_interval)

    try:
        if args.setup:
            if monitor.setup_credentials():
                print("Credentials setup completed!")
            else:
                print("Credentials setup failed!")
        elif args.test:
            if monitor.test_connection():
                print("✅ Test connection successful!")
            else:
                print("❌ Test connection failed!")
        else:
            monitor.start_monitoring()

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()