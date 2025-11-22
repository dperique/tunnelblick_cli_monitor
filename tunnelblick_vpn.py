#!/usr/bin/env python3

"""
Tunnelblick VPN CLI Manager

This script automates connecting to VPN through Tunnelblick on macOS.
It handles two-factor authentication with a prefix password + YubiKey token.

Examples:
    python3 tunnelblick_vpn.py connect MyVPNConfig
    python3 tunnelblick_vpn.py disconnect MyVPNConfig
    python3 tunnelblick_vpn.py status MyVPNConfig
    python3 tunnelblick_vpn.py list
"""

import subprocess
import sys
import time
import getpass
from typing import Optional, List
import argparse


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


def _get_vpn_configurations() -> List[str]:
    """
    Get list of available VPN configurations from Tunnelblick.

    Return Value(s):
        List[str]: List of VPN configuration names
    """
    script = '''
    tell application "Tunnelblick"
        get name of configurations
    end tell
    '''

    result = _run_applescript(script)
    if result:
        # Parse the AppleScript list format
        configs = result.replace('{', '').replace('}', '').split(', ')
        return [config.strip('"') for config in configs if config.strip()]
    return []


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
    print("Waiting for VPN connection...")
    for i in range(30):  # Wait up to 30 seconds
        status = _get_vpn_status(config_name)
        if status == "CONNECTED":
            return True
        elif "EXITING" in status or "DISCONNECTED" in status:
            return False
        time.sleep(1)
        print(f"  Checking connection status... ({i+1}/30)")

    return False


def _disconnect_vpn(config_name: str) -> bool:
    """
    Disconnect from the specified VPN configuration.

    Arg(s):
        config_name (str): Name of the VPN configuration
    Return Value(s):
        bool: True if disconnection was successful, False otherwise
    """
    script = f'''
    tell application "Tunnelblick"
        disconnect "{config_name}"
    end tell
    '''

    _run_applescript(script)

    # Wait for disconnection
    print("Disconnecting from VPN...")
    for i in range(10):
        status = _get_vpn_status(config_name)
        if "EXITING" in status or "DISCONNECTED" in status:
            return True
        time.sleep(1)

    return False


def list_configurations() -> None:
    """
    List all available VPN configurations.
    """
    configs = _get_vpn_configurations()
    if configs:
        print("Available VPN configurations:")
        for config in configs:
            status = _get_vpn_status(config)
            print(f"  • {config} ({status})")
    else:
        print("No VPN configurations found.")


def show_status(config_name: str) -> None:
    """
    Show the status of a specific VPN configuration.

    Arg(s):
        config_name (str): Name of the VPN configuration
    """
    status = _get_vpn_status(config_name)
    print(f"VPN '{config_name}' status: {status}")


def connect_vpn(config_name: str) -> None:
    """
    Connect to a VPN configuration with interactive password input.

    Arg(s):
        config_name (str): Name of the VPN configuration
    """
    # Check if already connected
    current_status = _get_vpn_status(config_name)
    if current_status == "CONNECTED":
        print(f"VPN '{config_name}' is already connected!")
        return

    print(f"Connecting to VPN: {config_name}")

    # Get complete password (prefix + YubiKey token)
    full_password = getpass.getpass("Password (prefix + YubiKey token): ")

    if not full_password:
        print("Error: Password cannot be empty")
        return

    print("Attempting to connect...")
    if _connect_vpn(config_name, full_password):
        print(f"✅ Successfully connected to VPN '{config_name}'!")
    else:
        print(f"❌ Failed to connect to VPN '{config_name}'")
        print("Please check your credentials and try again.")


def disconnect_vpn(config_name: str) -> None:
    """
    Disconnect from a VPN configuration.

    Arg(s):
        config_name (str): Name of the VPN configuration
    """
    current_status = _get_vpn_status(config_name)
    if "DISCONNECTED" in current_status or "EXITING" in current_status:
        print(f"VPN '{config_name}' is already disconnected!")
        return

    print(f"Disconnecting from VPN: {config_name}")
    if _disconnect_vpn(config_name):
        print(f"✅ Successfully disconnected from VPN '{config_name}'!")
    else:
        print(f"❌ Failed to disconnect from VPN '{config_name}'")


def main() -> None:
    """
    Main function to handle command line arguments and execute VPN operations.
    """
    parser = argparse.ArgumentParser(description='Tunnelblick VPN CLI Manager')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # List command
    subparsers.add_parser('list', help='List all VPN configurations')

    # Status command
    status_parser = subparsers.add_parser('status', help='Show status of a VPN configuration')
    status_parser.add_argument('config_name', help='Name of the VPN configuration')

    # Connect command
    connect_parser = subparsers.add_parser('connect', help='Connect to a VPN configuration')
    connect_parser.add_argument('config_name', help='Name of the VPN configuration')

    # Disconnect command
    disconnect_parser = subparsers.add_parser('disconnect', help='Disconnect from a VPN configuration')
    disconnect_parser.add_argument('config_name', help='Name of the VPN configuration')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == 'list':
            list_configurations()
        elif args.command == 'status':
            show_status(args.config_name)
        elif args.command == 'connect':
            connect_vpn(args.config_name)
        elif args.command == 'disconnect':
            disconnect_vpn(args.config_name)
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()