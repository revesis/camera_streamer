# Camera Streamer (Android Real-Time Ultra-Low Latency Camera Streaming)

A high-performance, ultra-low latency live camera streaming solution for Android devices to modern web browsers.

Features native Android camera support (zero third-party app installations required), Linux kernel V4L2 virtual webcam feed, and WebSocket + HTML5 Canvas zero-buffer rendering. Delivers rock-solid 30 FPS with sub-50ms end-to-end latency.

---

## 🌟 Key Features

- **Ultra-Low Latency (30~50ms)**: Direct feed via the Linux kernel `v4l2loopback` driver and WebSocket dispatch, eliminating container (MKV/MP4/FLV) buffering delays.
- **No Third-Party APK Needed**: Automatically controls the device's native camera application via ADB, bypassing vendor restrictions (such as ColorOS/MIUI install prompts and permission dialogs).
- **Clean Sensor Viewport**: Automatically crops the 3:4 aspect ratio camera viewfinder using `scrcpy` server-side hardware encoding, removing Android status bars and UI buttons.
- **Background Watchdog Guard**: Periodically checks the focused activity on the device. If the camera app times out or exits, it automatically relaunches in seconds.
- **Interactive Web Interface**:
  - 🎯 **Tap-to-Focus**: Click anywhere on the video feed in your browser to focus the device camera on that coordinate.
  - 🔄 **Camera Switching**: Toggle between front-facing and rear cameras with one click.
  - 📸 **Instant Snapshot**: Save uncompressed frames directly to your computer as JPEG without interrupting live video.
  - 📐 **Rotation & Fullscreen**: Rotate feed (90° / 180° / 270°) and enter immersive fullscreen mode.

---

## 🛠️ Prerequisites

- **Operating System**: Linux (Ubuntu, Debian, Arch Linux, Fedora, etc.)
- **System Utilities**:
  - `adb` (Android Platform Tools)
  - `scrcpy` (>= 2.0, recommended 3.x or 5.x)
  - `ffmpeg`
  - `v4l2loopback-dkms` (Kernel module)
- **Python Dependencies**:
  - `python >= 3.8`
  - `aiohttp`
  - `websockets`

### Package Installation

On Arch Linux:
```bash
sudo pacman -S android-tools scrcpy ffmpeg v4l2loopback-dkms python-aiohttp python-websockets
```

On Ubuntu / Debian:
```bash
sudo apt-get install adb scrcpy ffmpeg v4l2loopback-dkms python3-aiohttp python3-websockets
```

---

## 🚀 Quick Start

1. **Connect Your Android Device**:
   Enable Developer Options and USB Debugging on your phone, then connect via USB or TCP/IP:
   ```bash
   adb connect 172.17.131.136:38163
   ```

2. **Load V4L2 Loopback Kernel Module**:
   ```bash
   sudo modprobe v4l2loopback
   ```

3. **Start the Streaming Service**:
   ```bash
   chmod +x run_camera_stream.sh
   ./run_camera_stream.sh
   ```
   Or customize options using environment variables:
   ```bash
   ADB_SERIAL="172.17.131.136:38163" PORT=8080 ./run_camera_stream.sh
   ```

4. **Open in Browser**:
   Navigate to:
   - Local machine: `http://localhost:8080`
   - Other network devices: `http://<SERVER_IP>:8080`

---

## 📂 Project Structure

```
camera_streamer/
├── camera_streamer/
│   ├── camera_controller.py  # ADB device controller & background watchdog service
│   ├── stream_service.py     # V4L2 kernel device manager & FFmpeg/scrcpy pipeline
│   ├── server.py             # aiohttp async web server & WebSocket real-time router
│   └── web/
│       └── index.html        # Responsive web player (GPU Canvas + drop-frame decoder)
├── run_camera_stream.sh      # Startup script
├── .gitignore
└── README.md
```

---

## 📄 License
MIT License
