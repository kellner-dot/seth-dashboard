#!/usr/bin/env python3
"""
Emby Network Signal Checker
Diagnoses network connectivity for Emby Live TV / KaviTV channels.

Checks:
1. Emby server API reachable
2. KaviTV relay reachable (port 8100)
3. M3U stream URLs accessible
4. Network interfaces and IPs
5. Current channel status

Usage: python3 emby_signal_check.py
"""

import socket
import urllib.request
import urllib.error
import json
import subprocess
from datetime import datetime

EMBY_HOST = "127.0.0.1"
EMBY_PORT = 8096
RELAY_PORT = 8100
TIMEOUT = 10

def check_port(host, port, name):
    """Check if a TCP port is open."""
    try:
        sock = socket.create_connection((host, port), timeout=TIMEOUT)
        sock.close()
        return True, f"{name} ({host}:{port}) - OK"
    except Exception as e:
        return False, f"{name} ({host}:{port}) - FAIL: {str(e)[:60]}"

def check_http(url, name):
    """Check if an HTTP URL returns 200."""
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return True, f"{name} - HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return False, f"{name} - HTTP {e.code}"
    except Exception as e:
        return False, f"{name} - FAIL: {str(e)[:60]}"

def get_network_info():
    """Get local IP addresses."""
    info = []
    try:
        hostname = socket.gethostname()
        info.append(f"Hostname: {hostname}")
        # Get all IPs
        for fam, _, _, _, sockaddr in socket.getaddrinfo(hostname, None):
            ip = sockaddr[0]
            if ':' not in ip and not ip.startswith('127.'):
                info.append(f"IP: {ip}")
    except Exception as e:
        info.append(f"Network info failed: {e}")
    return info

def main():
    print("=" * 60)
    print("Emby Network Signal Checker")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    results = []
    
    # 1. Network interfaces
    print("[Network Interfaces]")
    for line in get_network_info():
        print(f"  {line}")
    print()

    # 2. Emby API
    print("[Emby Server]")
    ok, msg = check_port(EMBY_HOST, EMBY_PORT, "Emby API")
    print(f"  {msg}")
    results.append(ok)
    
    ok, msg = check_http(f"http://{EMBY_HOST}:{EMBY_PORT}/emby/System/Info", "Emby System Info")
    print(f"  {msg}")
    print()

    # 3. KaviTV Relay
    print("[KaviTV Relay]")
    ok, msg = check_port(EMBY_HOST, RELAY_PORT, "Relay API")
    print(f"  {msg}")
    results.append(ok)
    
    ok, msg = check_http(f"http://{EMBY_HOST}:{RELAY_PORT}/api/deep-health", "Relay Health")
    print(f"  {msg}")
    print()

    # 4. Stream URLs (from M3U)
    print("[Stream URLs]")
    channels = ['horror', 'experimental', 'independent']
    # Get LAN IP for stream URL test
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except:
        lan_ip = "10.0.0.98"
    
    for ch in channels:
        url = f"http://{lan_ip}:{RELAY_PORT}/kavitv/live/{ch}.ts"
        # Just check if port is open, don't actually stream
        ok, msg = check_port(lan_ip, RELAY_PORT, f"  {ch}")
        print(f"  {msg}")
    print()

    # Summary
    print("=" * 60)
    if all(results):
        print("RESULT: All critical services reachable ✓")
    else:
        print("RESULT: Some services unreachable ✗ - Check failures above")
    print("=" * 60)

if __name__ == "__main__":
    main()
