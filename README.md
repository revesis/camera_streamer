# Camera Streamer (Android Real-Time Ultra-Low Latency Camera Streaming)

A high-performance, ultra-low latency live camera streaming solution for Android devices to modern web browsers.

Features native Android camera support (zero third-party app installations required), Linux kernel V4L2 virtual webcam feed, and WebSocket + HTML5 Canvas zero-buffer rendering. Delivers rock-solid 30 FPS with sub-50ms end-to-end latency.

---

## 🌟 Key Features

- **Ultra-Low Latency (30~50ms)**: Direct feed via the Linux kernel `v4l2loopback` driver and WebSocket dispatch, eliminating container (MKV/MP4/FLV) buffering delays.
- **Physical Screen-Off Keep-Alive**: Automatically turns off the phone's physical screen panel (`scrcpy --turn-screen-off --stay-awake`), preventing phone heating, saving 90% display power, and avoiding OLED burn-in while streaming at full 30 FPS. Fully compatible with Android 11.
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
   Enable Developer Options and USB / Wireless Debugging on your phone:
   ```bash
   # Connect via wireless debugging (port dynamically assigned by Android):
   adb connect <PHONE_IP>:<PORT>

   # Or connect via USB cable directly.
   ```

2. **Load V4L2 Loopback Kernel Module**:
   ```bash
   sudo modprobe v4l2loopback
   ```

3. **Start the Streaming Service**:
   ```bash
   # 1) Auto-detect single device or launch interactive terminal selection menu:
   ./run_camera_stream.sh

   # 2) Specify target IP:Port directly as an argument:
   ./run_camera_stream.sh 172.17.131.136:37913

   # 3) Or pass flags (e.g. custom port or keep screen on):
   ./run_camera_stream.sh -s 172.17.131.136:37913 -p 8088 --keep-screen-on

   # 4) Or configure via environment variables:
   ADB_SERIAL="172.17.131.136:37913" PORT=8088 ./run_camera_stream.sh
   ```

4. **Open in Browser & Switch Devices on the Fly**:
   Navigate to `http://localhost:8088`.
   - Click the **Device Pill (⚙️)** in the top bar anytime to open the **ADB Device Selector**.
   - View all detected devices, switch between them with one click, or enter a new `IP:Port` dynamically without restarting the server!

---

## 📂 Project Structure

```
camera_streamer/
├── camera_streamer/
│   ├── adb_utils.py          # Dynamic ADB device discovery, connection & resolution
│   ├── camera_controller.py  # ADB device controller & background watchdog service
│   ├── stream_service.py     # V4L2 kernel device manager & FFmpeg/scrcpy pipeline
│   ├── server.py             # aiohttp async web server & WebSocket real-time router
│   └── web/
│       └── index.html        # Responsive web player (GPU Canvas + ADB device selector)
├── run_camera_stream.sh      # Startup script with auto-detection & CLI forwarding
├── .gitignore
└── README.md
```

---

## 📄 License
MIT License
