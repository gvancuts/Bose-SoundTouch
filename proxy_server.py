#!/usr/bin/env python3
"""
Proxy server for Bose SoundTouch controller.
Serves the HTML file and proxies API requests to the SoundTouch device.
Includes auto-discovery of SoundTouch devices on the local network.
"""

import http.server
import socketserver
import urllib.request
import urllib.error
import socket
import struct
import sys
import os
import json
import threading
import time
import re

# Parse command-line arguments
import argparse
parser = argparse.ArgumentParser(description='Proxy server for Bose SoundTouch controller.')
parser.add_argument('device_ip', nargs='?', default=os.environ.get('SOUNDTOUCH_DEVICE_IP') or None,
                    help='IP address of the SoundTouch device (env: SOUNDTOUCH_DEVICE_IP)')
parser.add_argument('-p', '--port', type=int, default=int(os.environ.get('SOUNDTOUCH_PORT', 8000)),
                    help='Port to run the server on (default: 8000, env: SOUNDTOUCH_PORT)')
args = parser.parse_args()

current_device_ip = args.device_ip
SOUNDTOUCH_PORT = 8090
PORT = args.port

# Store discovered devices
discovered_devices = {}
discovery_lock = threading.Lock()


def discover_soundtouch_devices(timeout=3):
    """
    Discover SoundTouch devices using SSDP (Simple Service Discovery Protocol).
    """
    global discovered_devices

    SSDP_ADDR = "239.255.255.250"
    SSDP_PORT = 1900

    # SSDP M-SEARCH message for UPnP devices
    ssdp_request = (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n"
        "MAN: \"ssdp:discover\"\r\n"
        "MX: 2\r\n"
        "ST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n"
        "\r\n"
    )

    devices = {}

    try:
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)

        # Send M-SEARCH request
        sock.sendto(ssdp_request.encode(), (SSDP_ADDR, SSDP_PORT))

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                data, addr = sock.recvfrom(4096)
                response = data.decode('utf-8', errors='ignore')

                # Check if it's a Bose SoundTouch device
                if 'Bose' in response or 'SoundTouch' in response:
                    ip = addr[0]
                    # Try to get device info
                    device_info = get_device_info(ip)
                    if device_info:
                        devices[ip] = device_info

            except socket.timeout:
                break
            except Exception as e:
                continue

        sock.close()

    except Exception as e:
        print(f"SSDP discovery error: {e}")

    # Also try direct scanning of common IP ranges if SSDP finds nothing
    if not devices:
        devices = scan_network_for_soundtouch()

    with discovery_lock:
        discovered_devices = devices

    return devices


def scan_network_for_soundtouch(timeout=1):
    """
    Scan local network for SoundTouch devices by checking port 8090.
    """
    devices = {}

    # Get local IP to determine network range
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "192.168.1.1"

    # Extract network prefix
    ip_parts = local_ip.split('.')
    network_prefix = '.'.join(ip_parts[:3])

    print(f"Scanning network {network_prefix}.0/24 for SoundTouch devices...")

    def check_ip(ip):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, SOUNDTOUCH_PORT))
            sock.close()

            if result == 0:
                device_info = get_device_info(ip)
                if device_info:
                    return ip, device_info
        except:
            pass
        return None

    # Use threading to speed up scanning
    threads = []
    results = []
    results_lock = threading.Lock()

    def check_and_store(ip):
        result = check_ip(ip)
        if result:
            with results_lock:
                results.append(result)

    for i in range(1, 255):
        ip = f"{network_prefix}.{i}"
        t = threading.Thread(target=check_and_store, args=(ip,))
        t.daemon = True
        threads.append(t)
        t.start()

        # Limit concurrent threads
        if len(threads) >= 50:
            for t in threads:
                t.join(timeout=2)
            threads = []

    # Wait for remaining threads
    for t in threads:
        t.join(timeout=2)

    for ip, info in results:
        devices[ip] = info

    return devices


def get_device_info(ip):
    """
    Get device information from a SoundTouch device.
    """
    try:
        url = f"http://{ip}:{SOUNDTOUCH_PORT}/info"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=2) as response:
            data = response.read().decode('utf-8')

            # Parse XML to extract name and type
            name_match = re.search(r'<name>([^<]+)</name>', data)
            type_match = re.search(r'<type>([^<]+)</type>', data)
            device_id_match = re.search(r'deviceID="([^"]+)"', data)

            if name_match:
                return {
                    'name': name_match.group(1),
                    'type': type_match.group(1) if type_match else 'Unknown',
                    'deviceId': device_id_match.group(1) if device_id_match else 'Unknown',
                    'ip': ip
                }
    except Exception as e:
        pass

    return None


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global current_device_ip

        # Discovery endpoint
        if self.path == '/discover':
            self.handle_discovery()
        # Get current device
        elif self.path == '/current-device':
            self.send_json_response({'ip': current_device_ip, 'devices': discovered_devices})
        # Proxy API requests to SoundTouch
        elif self.path.startswith('/api/'):
            if not current_device_ip:
                self.send_error(400, "No device selected. Please discover and select a device first.")
                return
            self.proxy_request('GET')
        else:
            # Serve static files
            super().do_GET()

    def do_POST(self):
        global current_device_ip

        # Set device endpoint
        if self.path == '/set-device':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            current_device_ip = data.get('ip')
            print(f"Device set to: {current_device_ip}")
            self.send_json_response({'success': True, 'ip': current_device_ip})
        elif self.path.startswith('/api/'):
            if not current_device_ip:
                self.send_error(400, "No device selected")
                return
            self.proxy_request('POST')
        else:
            self.send_error(404)

    def handle_discovery(self):
        """Handle device discovery request."""
        print("Starting device discovery...")
        devices = discover_soundtouch_devices(timeout=3)
        print(f"Found {len(devices)} device(s)")
        self.send_json_response(devices)

    def send_json_response(self, data):
        """Send a JSON response."""
        response = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(response))
        self.end_headers()
        self.wfile.write(response)

    def proxy_request(self, method):
        global current_device_ip

        # Remove /api prefix and check for device parameter
        path = self.path[4:]  # Remove '/api'

        # Check if a specific device IP is specified via query param
        target_ip = current_device_ip
        if '?device=' in path:
            path, device_ip = path.split('?device=')
            target_ip = device_ip.split('&')[0]  # Handle additional params

        url = f"http://{target_ip}:{SOUNDTOUCH_PORT}{path}"

        try:
            # Read request body for POST
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else None

            # Create request
            req = urllib.request.Request(url, data=body, method=method)
            req.add_header('Content-Type', 'application/xml')

            # Forward request
            with urllib.request.urlopen(req, timeout=10) as response:
                response_body = response.read()

                self.send_response(response.status)
                self.send_header('Content-Type', 'application/xml')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', len(response_body))
                self.end_headers()
                self.wfile.write(response_body)

        except urllib.error.URLError as e:
            self.send_error(502, f"Error connecting to SoundTouch: {e}")
        except Exception as e:
            self.send_error(500, f"Proxy error: {e}")

    def do_OPTIONS(self):
        # Handle CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        # Only log non-polling requests
        msg = format % args
        if '/api/now_playing' not in msg and '/api/volume' not in msg:
            print(f"[{self.log_date_time_string()}] {msg}")


# Change to the directory containing the HTML file
os.chdir(os.path.dirname(os.path.abspath(__file__)))

print(f"Starting SoundTouch proxy server on http://localhost:{PORT}")
if current_device_ip:
    print(f"Initial device: {current_device_ip}")
else:
    print("No device specified. Use discovery to find devices.")
print(f"Open http://localhost:{PORT}/soundtouch-controller-proxy.html in your browser")

# Allow socket reuse
socketserver.TCPServer.allow_reuse_address = True

with socketserver.TCPServer(("", PORT), ProxyHandler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
