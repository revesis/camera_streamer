# Android Sensor Agent (极简控制台 / 一键托管)

无需 ADB、超低延迟的 Android 手机后台传感器采集与 UDP 推流服务。

---

## 🌟 核心特性

- **脱离 ADB 依赖**：纯网络通信（Protobuf over UDP），无需开启 USB 调试，适合普通生产环境。
- **模块化可配置**：
  - 🔄 **IMU 惯性测量**：三轴加速度 + 三轴角速度陀螺仪 + 线性加速度（最高 200Hz+）
  - 🧭 **姿态估计**：原生旋转矢量，输出四元数 ($w, x, y, z$) 与欧拉角（Roll, Pitch, Yaw）
  - 🧲 **地磁计**：三轴微特斯拉磁场强度
  - 📷 **离屏摄像头**：无需界面预览，后台 `ImageReader` 捕获
- **熄屏物理黑屏保活**：持有 `PARTIAL_WAKE_LOCK` 与前台服务通知，按电源键彻底黑屏放入口袋依然持续推流。
- **下拉通知栏快捷磁贴 (Quick Settings Tile)**：无需打开 App 界面，通知栏直接一键启停。

---

## 🛠️ 构建与安装

### 1. 使用 Gradle 构建 APK
在 Android Studio 打开本目录，或在终端执行：
```bash
cd android_sensor_agent
./gradlew assembleDebug
```
生成的 APK 路径为：
`app/build/outputs/apk/debug/app-debug.apk`

### 2. 安装至手机
通过 USB 安装：
```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```
或者直接将 APK 发送至手机（微信、QQ、网盘、局域网传输）点击安装。

---

## 🚀 使用流程

1. **启动 PC 接收端**：
   在电脑终端运行 Python UDP 接收器：
   ```bash
   python3 -m camera_streamer.sensor_udp_receiver -p 9999 -v
   ```
   或直接启动主服务器：
   ```bash
   ./run_camera_stream.sh
   ```

2. **手机端配置**：
   - 打开 **Sensor Agent** 应用；
   - 输入电脑的局域网 IP（如 `192.168.1.100`）和 UDP 端口（默认 `9999`）；
   - 勾选需要采集的传感器模块（默认已开启 IMU 与四元数姿态）；
   - 点击 **“一键启动并托管后台”**。

3. **熄屏 / 后台无感运行**：
   - 启动后即可直接按 Home 键切出、或直接按电源键锁屏熄屏；
   - 状态栏会保留一条常驻通知，显示当前推流状态；
   - 也可将“传感器流”磁贴添加到通知栏控制中心，后续无需打开 App 即可一键启停。

---

## ⚙️ 国产手机（ColorOS / MIUI / OriginOS）后台保活设置

为了防止手机系统过于激进的电池省电策略在数小时后杀死后台服务，建议完成一次性设置：
1. **电池策略**：在手机「设置 -> 电池 -> 应用耗电管理 -> Sensor Agent」中，选择 **“允许完全后台行为 / 无限制”**。
2. **自启动**：允许“自启动”和“关联启动”。
