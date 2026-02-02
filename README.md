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

Or specify one or more device IPs and/or a custom port:

```bash
python3 proxy_server.py 192.168.1.100
python3 proxy_server.py 192.168.1.100 192.168.1.101
python3 proxy_server.py -p 9000
python3 proxy_server.py 192.168.1.100 192.168.1.101 -p 9000
```

Multiple IPs can also be passed via the `SOUNDTOUCH_DEVICE_IP` environment variable (comma-separated):

```bash
SOUNDTOUCH_DEVICE_IP=192.168.1.100,192.168.1.101 python3 proxy_server.py
```

Then open http://localhost:8000/soundtouch-controller-proxy.html in your browser (adjust the port if you changed it).

## Docker

Build the image:

```bash
docker build -t soundtouch .
```

If you know the device IP(s), standard port mapping is all you need:

```bash
docker run -p 8000:8000 -e SOUNDTOUCH_DEVICE_IP=192.168.1.50 soundtouch
docker run -p 8000:8000 -e SOUNDTOUCH_DEVICE_IP=192.168.1.50,192.168.1.60 soundtouch
```

To use auto-discovery (SSDP/network scan), `--net=host` is required because multicast traffic does not traverse Docker's default bridge network:

```bash
docker run --net=host soundtouch
```

Both `SOUNDTOUCH_PORT` and `SOUNDTOUCH_DEVICE_IP` can be set via environment variables:

```bash
docker run --net=host -e SOUNDTOUCH_PORT=9000 -e SOUNDTOUCH_DEVICE_IP=192.168.1.50 soundtouch
```

## Features

- **Auto-discovery** -- finds SoundTouch devices on your network via SSDP (falls back to subnet scan)
- **Playback controls** -- play/pause, next/previous track, presets, source selection
- **Volume control** -- slider, mute, per-device volume
- **Multi-room zones** -- create zones, add/remove speakers, control zone volume
- **No CORS issues** -- all API calls are proxied through the server
