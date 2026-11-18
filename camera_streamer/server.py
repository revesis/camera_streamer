import os
import sys
import json
import asyncio
import logging
import argparse
from aiohttp import web

# Ensure module and workspace directory are in sys.path
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from camera_controller import DeviceCameraController
from stream_service import CameraStreamManager
from adb_utils import get_adb_devices, connect_adb, disconnect_adb, resolve_serial
from sensor_udp_receiver import SensorUdpReceiver, frame_assembler
from camera_streamer.proto import sensor_packet_pb2

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(name)s: %(message)s'
)
logger = logging.getLogger("server")

INDEX_HTML_PATH = os.path.join(os.path.dirname(__file__), "web", "index.html")

# Global device state
current_serial = None
controller = DeviceCameraController()
stream_mgr = CameraStreamManager()

# Global sensor state & receiver
latest_sensor_data = {}
sensor_clients = set()


def on_sensor_packet(pkt, addr):
    global latest_sensor_data
    data = {
        "seq": pkt.sequence_number,
        "timestamp_ns": pkt.timestamp_ns,
        "device_id": pkt.device_id,
        "remote_ip": addr[0]
    }
    if pkt.HasField("imu"):
        data["imu"] = {
            "accel": {"x": pkt.imu.accel.x, "y": pkt.imu.accel.y, "z": pkt.imu.accel.z},
            "gyro": {"x": pkt.imu.gyro.x, "y": pkt.imu.gyro.y, "z": pkt.imu.gyro.z},
            "linear_accel": {"x": pkt.imu.linear_accel.x, "y": pkt.imu.linear_accel.y, "z": pkt.imu.linear_accel.z}
        }
    if pkt.HasField("orientation"):
        q = pkt.orientation.rotation_vector
        euler = pkt.orientation.euler_angles
        data["orientation"] = {
            "quaternion": {"w": q.w, "x": q.x, "y": q.y, "z": q.z, "accuracy": q.accuracy},
            "euler": {"roll": euler.x, "pitch": euler.y, "yaw": euler.z}
        }
    if pkt.HasField("mag"):
        data["mag"] = {"x": pkt.mag.magnetic_field.x, "y": pkt.mag.magnetic_field.y, "z": pkt.mag.magnetic_field.z}
    if pkt.HasField("env"):
        data["env"] = {"pressure": pkt.env.pressure, "light": pkt.env.light, "temp": pkt.env.temperature}
    if pkt.HasField("camera_frame"):
        cf = pkt.camera_frame
        assembled = frame_assembler.add_chunk(cf.frame_id, cf.chunk_index, cf.total_chunks, cf.payload)
        if assembled:
            stream_mgr.push_frame(assembled)
            data["camera_frame"] = {"width": cf.width, "height": cf.height, "bytes": len(assembled)}

    if pkt.HasField("device_status"):
        ds = pkt.device_status
        data["device_status"] = {
            "battery_level": ds.battery_level,
            "is_charging": ds.is_charging,
            "battery_temp": round(ds.battery_temp, 1),
            "is_front_camera": ds.is_front_camera,
            "ip_address": ds.ip_address
        }
    elif "device_status" in latest_sensor_data:
        data["device_status"] = latest_sensor_data["device_status"]
    
    latest_sensor_data = data


sensor_receiver = SensorUdpReceiver(port=int(os.environ.get("SENSOR_PORT", "9999")), on_packet=on_sensor_packet)


def switch_target_device(new_serial: str | None):
    """Dynamically switch camera controller and streaming pipeline to a new target device."""
    global current_serial
    old_serial = current_serial
    current_serial = new_serial
    logger.info("Switching active ADB device: '%s' -> '%s'", old_serial, current_serial)
    controller.update_serial(current_serial)
    stream_mgr.update_serial(current_serial)


routes = web.RouteTableDef()


@routes.get('/')
@routes.get('/index.html')
async def index_handler(request):
    try:
        return web.FileResponse(INDEX_HTML_PATH)
    except Exception as e:
        return web.Response(text=f"Error reading index.html: {e}", status=500)


@routes.get('/ws')
async def websocket_handler(request):
    ws = web.WebSocketResponse(heartbeat=20.0)
    await ws.prepare(request)
    logger.info("WebSocket client connected from %s", request.remote)

    last_frame_id = -1
    try:
        while not ws.closed:
            frame = stream_mgr.get_latest_frame()
            current_id = stream_mgr.frame_id
            if frame and current_id != last_frame_id:
                last_frame_id = current_id
                await ws.send_bytes(frame)
            await asyncio.sleep(0.015)  # Snappy frame dispatch
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    except Exception as e:
        logger.debug("WS connection error: %s", e)
    finally:
        logger.info("WebSocket client disconnected: %s", request.remote)
    return ws


@routes.get('/stream.mjpg')
async def mjpeg_handler(request):
    response = web.StreamResponse(
        status=200,
        headers={
            'Age': '0',
            'Cache-Control': 'no-cache, private, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Content-Type': 'multipart/x-mixed-replace; boundary=frame'
        }
    )
    await response.prepare(request)
    last_frame_id = -1

    try:
        while True:
            frame = stream_mgr.get_latest_frame()
            current_id = stream_mgr.frame_id
            if frame and current_id != last_frame_id:
                last_frame_id = current_id
                part = (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n'
                    b'Content-Length: ' + str(len(frame)).encode('ascii') + b'\r\n\r\n' +
                    frame + b'\r\n'
                )
                await response.write(part)
            await asyncio.sleep(0.035)
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    return response


@routes.get('/api/snapshot')
async def snapshot_handler(request):
    frame = stream_mgr.get_latest_frame()
    if frame:
        return web.Response(body=frame, content_type='image/jpeg', headers={'Cache-Control': 'no-cache'})
    return web.Response(text="No frame available", status=503)


@routes.get('/api/status')
async def status_handler(request):
    device_status = latest_sensor_data.get("device_status")
    data = {
        "serial": current_serial,
        "connected": current_serial is not None or stream_mgr.latest_frame is not None or bool(latest_sensor_data),
        "running": stream_mgr.running,
        "screen_off": stream_mgr.turn_screen_off,
        "fps": round(stream_mgr.fps, 1),
        "has_frame": stream_mgr.latest_frame is not None,
        "sensor_active": sensor_receiver.stats is not None and sensor_receiver.stats.total_packets > 0,
        "sensor_device": latest_sensor_data.get("device_id"),
        "device_status": device_status,
        "battery_level": device_status.get("battery_level") if device_status else None,
        "is_charging": device_status.get("is_charging") if device_status else None,
        "battery_temp": device_status.get("battery_temp") if device_status else None,
        "is_front_camera": device_status.get("is_front_camera") if device_status else None,
    }
    return web.json_response(data, headers={'Access-Control-Allow-Origin': '*'})


@routes.get('/api/devices')
async def devices_handler(request):
    devices = get_adb_devices()
    return web.json_response({
        "current_serial": current_serial,
        "devices": devices
    }, headers={'Access-Control-Allow-Origin': '*'})


@routes.post('/api/connect')
async def connect_handler(request):
    try:
        req_data = await request.json()
    except Exception:
        req_data = {}

    target = str(req_data.get("serial", "")).strip()
    auto = req_data.get("auto", False)

    if auto or not target:
        detected = resolve_serial(interactive=False)
        if not detected:
            return web.json_response({
                "ok": False,
                "message": "No active ADB devices found. Please specify target IP:Port."
            }, status=400)
        target = detected

    if ":" in target:
        success, msg = connect_adb(target)
        if not success:
            return web.json_response({
                "ok": False,
                "message": f"Failed to connect to {target}: {msg}"
            }, status=400)

    switch_target_device(target)
    return web.json_response({
        "ok": True,
        "serial": current_serial,
        "message": f"Successfully connected to {current_serial}"
    })


@routes.post('/api/disconnect')
async def disconnect_handler(request):
    old = current_serial
    if old and ":" in old:
        disconnect_adb(old)
    switch_target_device(None)
    return web.json_response({"ok": True, "message": "Device disconnected"})


@routes.post('/api/switch_camera')
async def switch_camera_handler(request):
    logger.info("Switch camera requested via /api/switch_camera")
    http_switched = False
    udp_sent = False
    adb_switched = False

    # 1. Direct HTTP control to phone if phone IP is known or on subnet
    phone_ip = latest_sensor_data.get("device_status", {}).get("ip_address")
    if not phone_ip:
        remote_ip = latest_sensor_data.get("remote_ip")
        if remote_ip and not remote_ip.startswith("192.168.111.") and not remote_ip.startswith("127."):
            phone_ip = remote_ip
        else:
            phone_ip = "172.17.131.136"

    if phone_ip:
        try:
            url = f"http://{phone_ip}:8089/switch_camera"
            logger.info(f"Sending direct HTTP switch_camera to: {url}")
            import aiohttp
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2.0)) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        http_switched = True
                        res_json = await resp.json()
                        logger.info(f"Direct HTTP switch_camera successful: {res_json}")
                        if "is_front_camera" in res_json:
                            if "device_status" not in latest_sensor_data:
                                latest_sensor_data["device_status"] = {}
                            latest_sensor_data["device_status"]["is_front_camera"] = res_json["is_front_camera"]
        except Exception as e:
            logger.warning(f"Direct HTTP switch_camera to {phone_ip}:8089 failed: {e}")

    # 2. UDP ControlPacket (fallback if HTTP direct control not used)
    if not http_switched and sensor_receiver.last_sender_addr:
        ctrl = sensor_packet_pb2.ControlPacket()
        ctrl.command = sensor_packet_pb2.ControlPacket.Command.SWITCH_CAMERA
        ctrl.param = 1
        udp_sent = sensor_receiver.send(ctrl.SerializeToString())
        logger.info(f"UDP ControlPacket(SWITCH_CAMERA) sent: {udp_sent} to {sensor_receiver.last_sender_addr}")

    # 3. ADB Intent fallback (only if both HTTP and UDP failed)
    if not http_switched and not udp_sent:
        import subprocess
        target_devices = []
        if current_serial:
            target_devices.append(current_serial)
        else:
            for d in get_adb_devices():
                if d not in target_devices:
                    target_devices.append(d)

        if not target_devices:
            try:
                res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=2)
                for line in res.stdout.strip().splitlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == "device":
                        target_devices.append(parts[0])
            except Exception:
                pass

        for dev in target_devices:
            try:
                subprocess.run(
                    ["adb", "-s", dev, "shell", "am", "broadcast", "-a", "com.antigravity.sensoragent.SWITCH_CAMERA"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
                )
                subprocess.run(
                    ["adb", "-s", dev, "shell", "am", "start-foreground-service", "-a", "com.antigravity.sensoragent.SWITCH_CAMERA", "com.antigravity.sensoragent/.service.SensorForegroundService"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
                )
                adb_switched = True
                logger.info(f"ADB SWITCH_CAMERA intent sent to {dev}")
            except Exception as e:
                logger.warning(f"ADB switch_camera on {dev} failed: {e}")

    return web.json_response({
        "ok": http_switched or udp_sent or adb_switched,
        "action": "switch_camera",
        "http": http_switched,
        "udp": udp_sent,
        "adb": adb_switched
    })


@routes.post('/api/focus')
async def focus_handler(request):
    if not current_serial:
        return web.json_response({"ok": False, "error": "No device connected"}, status=400)
    try:
        req_data = await request.json()
    except Exception:
        req_data = {}
    rel_x = float(req_data.get("rel_x", 0.5))
    rel_y = float(req_data.get("rel_y", 0.5))
    controller.tap_focus(rel_x, rel_y)
    return web.json_response({"ok": True, "action": "focus", "rel_x": rel_x, "rel_y": rel_y})


@routes.post('/api/shutter')
async def shutter_handler(request):
    if not current_serial:
        return web.json_response({"ok": False, "error": "No device connected"}, status=400)
    controller.trigger_shutter()
    return web.json_response({"ok": True, "action": "shutter"})


@routes.post('/api/wake')
async def wake_handler(request):
    if not current_serial:
        return web.json_response({"ok": False, "error": "No device connected"}, status=400)
    controller.ensure_camera_active()
    return web.json_response({"ok": True, "action": "wake"})


@routes.post('/api/screen_power')
async def screen_power_handler(request):
    if not current_serial:
        return web.json_response({"ok": False, "error": "No device connected"}, status=400)
    try:
        req_data = await request.json()
    except Exception:
        req_data = {}

    action = req_data.get("action", "toggle")
    if action == "off":
        new_state = True
    elif action == "on":
        new_state = False
    else:  # toggle
        new_state = not stream_mgr.turn_screen_off

    stream_mgr.set_screen_off(new_state)
    if not new_state:
        controller.wake_screen()

    return web.json_response({
        "ok": True,
        "screen_off": stream_mgr.turn_screen_off,
        "message": "Screen turned off" if stream_mgr.turn_screen_off else "Screen turned on"
    })


@routes.get('/api/sensor/status')
async def sensor_status_handler(request):
    stats = sensor_receiver.stats
    return web.json_response({
        "ok": True,
        "active": stats is not None and stats.total_packets > 0,
        "rate_hz": round(stats.current_fps, 1) if stats else 0.0,
        "throughput_kbps": round(stats.current_kbps, 1) if stats else 0.0,
        "total_packets": stats.total_packets if stats else 0,
        "lost_packets": stats.lost_packets if stats else 0,
        "loss_rate_pct": round(stats.loss_rate_percent, 2) if stats else 0.0,
        "latest": latest_sensor_data
    })


@routes.get('/ws/sensor')
async def ws_sensor_handler(request):
    ws = web.WebSocketResponse(heartbeat=20.0)
    await ws.prepare(request)
    sensor_clients.add(ws)
    last_seq = -1
    try:
        while not ws.closed:
            if latest_sensor_data and latest_sensor_data.get("seq") != last_seq:
                last_seq = latest_sensor_data.get("seq")
                await ws.send_json(latest_sensor_data)
            await asyncio.sleep(0.02)  # ~50Hz web telemetry rate
    except Exception:
        pass
    finally:
        sensor_clients.discard(ws)
    return ws


async def on_startup(app):
    if current_serial:
        logger.info("Initializing camera on device %s...", current_serial)
        controller.ensure_camera_active()
    else:
        logger.info("Server started in standby mode (no device bound). You can connect via Web UI or /api/connect.")
    controller.start_watchdog()

    logger.info("Starting video stream manager...")
    stream_mgr.start()

    logger.info("Starting UDP sensor receiver...")
    await sensor_receiver.start()


async def on_cleanup(app):
    logger.info("Shutting down...")
    sensor_receiver.stop()
    controller.stop_watchdog()
    stream_mgr.stop()
    logger.info("Cleanup completed.")


def create_app():
    app = web.Application()
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


def parse_args():
    parser = argparse.ArgumentParser(description="Realme Ultra-Low Latency Camera Streaming Server")
    parser.add_argument("-s", "--serial", dest="serial", default=None,
                        help="ADB device serial or network endpoint (e.g. 172.17.131.136:37913)")
    parser.add_argument("-p", "--port", dest="port", type=int,
                        default=int(os.environ.get("PORT", "8088")),
                        help="Web server HTTP port (default: 8088 or $PORT)")
    parser.add_argument("--host", dest="host",
                        default=os.environ.get("HOST", "0.0.0.0"),
                        help="Web server bind host (default: 0.0.0.0 or $HOST)")
    parser.add_argument("--no-interactive", action="store_true",
                        help="Disable interactive terminal menu when selecting ADB devices")
    parser.add_argument("--keep-screen-on", action="store_true",
                        help="Keep device physical screen turned on during streaming")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.keep_screen_on:
        stream_mgr.turn_screen_off = False
        logger.info("Screen-off mode disabled: device physical screen will stay on.")

    # Dynamic device resolution
    if args.serial == "":
        resolved_device = None
        logger.info("Explicit empty serial passed: running in pure receiver / Sensor Agent mode without ADB.")
    else:
        resolved_device = resolve_serial(
            cli_serial=args.serial,
            interactive=not args.no_interactive
        )
    switch_target_device(resolved_device)

    app = create_app()
    logger.info("Camera Stream Server starting on http://%s:%d", args.host, args.port)
    web.run_app(app, host=args.host, port=args.port, print=None)
