# Camera Streamer (Android 实时极速摄像头流媒体服务)

将 Android 设备的摄像头媒体流引出并通过浏览器实时观看的高性能、极速低延迟流媒体解决方案。

支持原生相机免安装第三方 App、支持 Linux 内核级 V4L2 虚拟摄像头直推、WebSocket + HTML5 Canvas 零缓冲解码，实测稳定 30FPS，端到端延迟低至 30~50ms。

---

## 🌟 核心特性

- **极速低延迟 (30~50ms)**：通过 Linux 内核 `v4l2loopback` 模块和 WebSocket 直推，彻底摒弃文件和封装格式（如 MKV、FLV）的积压延迟。
- **免安装 App，开箱即用**：利用 ADB 自动拉起 Android 系统原生相机，避开厂商系统（如 ColorOS/MIUI）的权限拦截与安装确认。
- **纯净传感器取景**：通过 `scrcpy` 硬件编码器自动进行取景框裁切（3:4 比例），滤除手机状态栏和相机操作控件。
- **后台智能看门狗 (Watchdog)**：自动监测前台相机 Activity，防止手机息屏或相机超时退出，断线自动秒级拉起。
- **丰富的网页端交互控制**：
  - 🎯 **点击画面对焦**：在网页任意位置点击，自动同步触发手机屏幕测光与自动对焦。
  - 🔄 **切换前后摄像头**：一键切换手机前置自拍与后置主摄。
  - 📸 **瞬时高清截图**：无损保存当前帧为 JPEG 图片，不打断手机相机录像预览。
  - 📐 **画面旋转与全屏**：支持 90°/180°/270° 旋转与沉浸式全屏监控。

---

## 🛠️ 依赖环境

- **操作系统**：Linux (Ubuntu / Debian / Arch Linux 等)
- **核心工具**：
  - `adb` (Android Platform Tools)
  - `scrcpy` (>= 2.0，推荐 3.x 或 5.x)
  - `ffmpeg`
  - `v4l2loopback-dkms` (内核模块)
- **Python 依赖**：
  - `python >= 3.8`
  - `aiohttp`
  - `websockets`

在 Arch Linux 上安装依赖：
```bash
sudo pacman -S android-tools scrcpy ffmpeg v4l2loopback-dkms python-aiohttp python-websockets
```

在 Ubuntu / Debian 上安装依赖：
```bash
sudo apt-get install adb scrcpy ffmpeg v4l2loopback-dkms python3-aiohttp python3-websockets
```

---

## 🚀 快速启动

1. **连接 Android 手机**：
   确保手机已开启「开发者选项」及「USB 调试」，并通过 USB 或 WiFi 连接：
   ```bash
   adb connect 172.17.131.136:38163
   ```

2. **加载 V4L2 内核模块**：
   ```bash
   sudo modprobe v4l2loopback
   ```

3. **启动流媒体服务**：
   ```bash
   chmod +x run_camera_stream.sh
   ./run_camera_stream.sh
   ```
   或者通过环境变量自定义参数：
   ```bash
   ADB_SERIAL="172.17.131.136:38163" PORT=8080 ./run_camera_stream.sh
   ```

4. **在浏览器中观看**：
   打开浏览器访问：
   - 本机：`http://localhost:8080`
   - 局域网其它设备：`http://<SERVER_IP>:8080`

---

## 📂 架构与文件结构

```
camera_streamer/
├── camera_streamer/
│   ├── camera_controller.py  # ADB 控制器与后台看门狗保活
│   ├── stream_service.py     # V4L2 内核驱动管理与 FFmpeg/scrcpy 吞吐管道
│   ├── server.py             # aiohttp 异步 Web 服务器与 WebSocket 分发
│   └── web/
│       └── index.html        # 响应式 Web 播放器与交互控制面板
├── run_camera_stream.sh      # 一键启动守护脚本
├── .gitignore
└── README.md
```

---

## 📄 License
MIT License
