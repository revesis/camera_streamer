# Camera Streamer & Android Sensor Agent

A high-performance, ultra-low latency live camera streaming and sensor telemetry system for Android devices to modern web browsers.

Supports **two flexible architectures**:
1. **Zero-APK Mode (via ADB & Native Camera)**: Controls the device's built-in camera app over ADB with hardware-accelerated `scrcpy` crop and Linux `v4l2loopback` virtual webcam feed.
2. **Headless Sensor Agent Mode (100% ADB-Free & Protobuf over UDP)**: Runs a dedicated Android background foreground service (`android_sensor_agent`) that captures raw frames via Camera2 API and high-frequency IMU / quaternion / magnetometer data, packaging them over UDP using Protocol Buffers with sub-50ms latency — streaming continuously even when the physical screen is completely turned off and locked.

---

## 🌟 Key Features

### 📡 Android Sensor Agent (Headless & UDP Protobuf)
- **Zero ADB Dependency**: Operates over standard WiFi / UDP network sockets without maintaining an active ADB connection.
- **True Screen-Off / Headless Streaming**: Utilizes Android `Camera2` API and background `ForegroundService` with `PARTIAL_WAKE_LOCK`. Does not launch any foreground system camera apps; streams smoothly while the screen is physically dark or locked.
- **High-Frequency Telemetry (Up to 200 Hz)**:
  - 🔄 **IMU**: 3-axis Accelerometer & Gyroscope at up to 200 Hz (`SENSOR_DELAY_FASTEST`).
  - 🧭 **Orientation**: Rotation Vector Quaternions & Euler Angles (Roll / Pitch / Yaw).
  - 🧲 **Magnetometer**: 3-axis microtesla magnetic field data.
  - 🔋 **Device Status**: Live battery capacity percentage, charging status, and battery temperature (°C).
- **Camera Hot-Switching**: Dynamic toggle between **Front** and **Rear** camera sensors on the fly, either directly in the Android app UI or remotely from the Web console.
- **MTU-Safe UDP Chunking**: Large JPEG frames (~35KB-120KB) are sliced into 1100-byte UDP datagrams with automatic frame ID and chunk reassembly on the receiver side.
- **Docker / Podman Zero-JDK Build**: Compile the Android APK inside an isolated container (`ghcr.io/cirruslabs/android-sdk:34`) without installing Java/JDK or Android SDK on the host machine.

### 🎥 Native Camera App Mode (via ADB & scrcpy)
- **Ultra-Low Latency (30~50ms)**: Direct feed via the Linux kernel `v4l2loopback` driver and WebSocket dispatch, eliminating container (MKV/MP4/FLV) buffering delays.
- **Physical Screen-Off Keep-Alive**: Automatically turns off the phone's physical screen panel (`scrcpy --turn-screen-off --stay-awake`), preventing overheating and OLED burn-in while streaming at full 30 FPS.
- **No Third-Party APK Needed**: Automatically controls the device's native camera application via ADB, bypassing vendor restrictions (such as ColorOS/MIUI install prompts and permission dialogs).
- **Clean Sensor Viewport**: Automatically crops the 3:4 aspect ratio camera viewfinder using `scrcpy` server-side hardware encoding, removing Android status bars and UI buttons.
- **Background Watchdog Guard**: Periodically checks the focused activity on the device. If the camera app times out or exits, it automatically relaunches in seconds.

### 🌐 Modern Responsive Web Console
- **Zero-Buffer GPU Canvas**: WebSocket direct frame stream decoded and painted to HTML5 Canvas.
- **500x200 Responsive Layout**: Automatically adapts to compact windows, mini PiP (Picture-in-Picture) widgets, and embeds without scrollbars.
- **Live Battery & Thermal Indicator**: Real-time badge in the top bar showing phone battery percentage and Celsius temperature (`🔋 74% (24.5°C)`).
- **One-Click Remote Camera Switch**: Toggle front/rear camera with instant feedback.
- **Interactive Controls**:
  - 🎯 **Tap-to-Focus**: Click anywhere on the video feed to focus the device camera at that coordinate (ADB mode).
  - 📸 **Instant Snapshot**: Download full-resolution JPEG frames directly without interrupting streaming.
  - 🌙 **Physical Screen Toggle**: Turn phone display panel on/off on demand.
  - 📐 **Rotation & Fullscreen**: 90° rotation increments and browser fullscreen mode.
  - 📱 **Dynamic ADB Device Selector**: Discover, connect to wireless debugging endpoints, and switch devices on the fly without server restarts.

---

## 🛠️ Prerequisites

### Host System Requirements (Linux)
- **OS**: Linux (Ubuntu, Debian, Arch Linux, Fedora, etc.)
- **System Utilities** (for ADB mode):
  - `adb` (Android Platform Tools)
  - `scrcpy` (>= 2.0, recommended 3.x)
  - `ffmpeg`
  - `v4l2loopback-dkms` (Linux kernel module)
- **Container Engine** (for building Android APK):
  - `podman` or `docker` (Host JDK **not** required)
- **Python Dependencies**:
  - `python >= 3.8`
  - `aiohttp`
  - `protobuf >= 4.21`

### Package Installation

On Arch Linux:
```bash
sudo pacman -S android-tools scrcpy ffmpeg v4l2loopback-dkms python-aiohttp protobuf podman
```

On Ubuntu / Debian:
```bash
sudo apt-get install adb scrcpy ffmpeg v4l2loopback-dkms python3-aiohttp python3-protobuf podman
```

---

## 🚀 Quick Start

### Option A: Headless Sensor Agent Mode (Recommended)

1. **Build the Android APK (Zero-JDK via Podman)**:
   ```bash
   podman run --rm -v $(pwd):/workspace:z ghcr.io/cirruslabs/android-sdk:34 /workspace/android_sensor_agent/build_in_docker.sh
   ```
   The compiled APK will be generated at `android_sensor_agent/app/build/outputs/apk/debug/app-debug.apk`.

2. **Install & Launch Sensor Agent on Phone**:
   ```bash
   adb install -r android_sensor_agent/app/build/outputs/apk/debug/app-debug.apk
   ```
   Open the **Sensor Agent** app on your phone:
   - Enter your PC / Relay IP (e.g., `192.168.1.100` or Windows forwarder `10.40.11.44`) and UDP port (`9999`).
   - Toggle desired modules: **IMU**, **Orientation**, **Magnetometer**, or **Headless Camera (离屏摄像头)**.
   - Tap **「一键启动并托管后台」** (Start Background Service).
   - *Tip*: You can now turn off the screen or lock the phone. The service will continue streaming in the background!

3. **Start the Web Streaming Server (Non-ADB mode)**:
   ```bash
   python3 camera_streamer/server.py --serial "" --no-interactive -p 8088
   ```

4. **(Optional) Cross-Subnet / Windows UDP Forwarder**:
   If running behind a Windows host or NAT bridge, run the included Python bidirectional UDP relay:
   ```bash
   python3 udp_forward.py
   ```

5. **Open Browser**:
   Navigate to `http://localhost:8088` (or your host IP `http://192.168.x.x:8088`).

---

### Option B: Zero-APK ADB Mode (Native Camera App)

1. **Connect Your Android Device**:
   ```bash
   # Connect via wireless debugging:
   adb connect <PHONE_IP>:<PORT>
   # Or connect via USB cable directly.
   ```

2. **Load V4L2 Loopback Kernel Module**:
   ```bash
   sudo modprobe v4l2loopback
   ```

3. **Start the Streaming Service**:
   ```bash
   # Auto-detect device and start:
   ./run_camera_stream.sh
   ```

4. **Open in Browser**:
   Navigate to `http://localhost:8088`.

---

## 📐 Responsive Layout & 500x200 Mini-Widget

The web interface is fully responsive:
- **Standard Desktop View (>600px)**: Complete management console with large cards, stream telemetry, and expanded control buttons.
- **Compact View (500x200 / Mini PiP Widget)**: Automatically converts into an ultra-compact, borderless live monitor. Status and battery indicators float in a sleek top bar, controls shrink into micro-buttons (`切换`, `熄屏`, `截图`, `唤醒`, `全屏`), and the canvas fits edge-to-edge with zero scrollbars.

---

## 📂 Project Structure

```
camera_streamer/
├── android_sensor_agent/             # Android Headless Sensor & Camera Agent
│   ├── app/
│   │   ├── src/main/java/.../
│   │   │   ├── collector/            # Camera2, IMU, Magnetometer, Battery collectors
│   │   │   ├── net/                  # UdpDispatcher (Protobuf UDP sender & receiver)
│   │   │   ├── service/              # SensorForegroundService & partial WakeLock
│   │   │   └── ui/                   # MainActivity management console
│   │   ├── src/main/proto/           # sensor_packet.proto definitions
│   │   └── src/main/res/             # Dark theme UI layouts & vector icons
│   ├── build_in_docker.sh            # Isolated Podman/Docker compile script (No host JDK)
│   └── build.gradle.kts
├── camera_streamer/
│   ├── proto/                        # Protobuf protocol definitions & Python bindings
│   │   ├── sensor_packet.proto       # SensorPacket, DeviceStatus, ControlPacket
│   │   └── sensor_packet_pb2.py
│   ├── sensor_udp_receiver.py        # Asyncio UDP receiver, stats & frame chunk assembler
│   ├── adb_utils.py                  # ADB device discovery, connection & auto-resolution
│   ├── camera_controller.py          # Native camera ADB controller & watchdog
│   ├── stream_service.py             # V4L2 virtual camera manager & scrcpy pipeline
│   ├── server.py                     # aiohttp async web server & multi-client stream hub
│   └── web/
│       └── index.html                # Responsive web player (Full Desktop + 500x200 layout)
├── tests/
│   ├── test_dynamic_adb.py           # Unit tests for ADB utils
│   └── test_sensor_udp.py            # Unit tests for UDP packet parser & chunk assembler
├── run_camera_stream.sh              # Unified CLI launcher script
├── .gitignore
└── README.md
```

---

## 🔌 API Reference

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/` | `GET` | Live streaming web console. |
| `/stream.mjpg` | `GET` | Standard MJPEG stream endpoint for third-party tools (OBS, VLC, OpenCV). |
| `/ws` | `WS` | Ultra-low latency binary WebSocket frame feed. |
| `/ws/sensor` | `WS` | Real-time JSON telemetry broadcast (IMU, Quaternions, Battery). |
| `/api/status` | `GET` | Current device connectivity, battery status, temperature, and camera orientation. |
| `/api/snapshot` | `GET` | Capture and download the latest uncompressed JPEG frame. |
| `/api/switch_camera` | `POST` | Remotely switch between Front and Rear cameras via UDP / ADB. |
| `/api/screen_power` | `POST` | Toggle physical phone screen panel on/off. |
| `/api/devices` | `GET` | List all discovered ADB devices. |
| `/api/connect` | `POST` | Dynamically bind to a target ADB `IP:Port`. |

---

## 📄 License
MIT License
