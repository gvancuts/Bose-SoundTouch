# Bose SoundTouch Controller

A web-based controller for Bose SoundTouch 10 speakers. A Python proxy server serves the web UI and forwards commands to SoundTouch devices on your local network.

## Requirements

- Python 3.6+
- No external dependencies

## Usage

Start the server:

```bash
python3 proxy_server.py
```

Or specify a device IP and/or a custom port:

```bash
python3 proxy_server.py 192.168.1.100
python3 proxy_server.py -p 9000
python3 proxy_server.py 192.168.1.100 -p 9000
```

Then open http://localhost:8000/soundtouch-controller-proxy.html in your browser (adjust the port if you changed it).

## Docker

Build the image:

```bash
docker build -t soundtouch .
```

Run with default settings (port 8000, auto-discovery):

```bash
docker run --net=host soundtouch
```

Run with a custom port and device IP:

```bash
docker run --net=host -e SOUNDTOUCH_PORT=9000 -e SOUNDTOUCH_DEVICE_IP=192.168.1.50 soundtouch
```

`--net=host` is required so the container can reach SoundTouch devices on your LAN and perform SSDP discovery.

## Features

- **Auto-discovery** -- finds SoundTouch devices on your network via SSDP (falls back to subnet scan)
- **Playback controls** -- play/pause, next/previous track, presets, source selection
- **Volume control** -- slider, mute, per-device volume
- **Multi-room zones** -- create zones, add/remove speakers, control zone volume
- **No CORS issues** -- all API calls are proxied through the server
