import os
import sys
import json
import asyncio
import logging
import argparse
from aiohttp import web

# Ensure current module directory is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

from camera_controller import DeviceCameraController
from stream_service import CameraStreamManager
from adb_utils import get_adb_devices, connect_adb, disconnect_adb, resolve_serial

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
    data = {
        "serial": current_serial,
        "connected": current_serial is not None,
        "running": stream_mgr.running,
        "fps": round(stream_mgr.fps, 1),
        "has_frame": stream_mgr.latest_frame is not None
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
    if not current_serial:
        return web.json_response({"ok": False, "error": "No device connected"}, status=400)
    controller.switch_camera()
    return web.json_response({"ok": True, "action": "switch_camera"})


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


async def on_startup(app):
    if current_serial:
        logger.info("Initializing camera on device %s...", current_serial)
        controller.ensure_camera_active()
    else:
        logger.info("Server started in standby mode (no device bound). You can connect via Web UI or /api/connect.")
    controller.start_watchdog()

    logger.info("Starting video stream manager...")
    stream_mgr.start()


async def on_cleanup(app):
    logger.info("Shutting down...")
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
                        default=int(os.environ.get("PORT", "8080")),
                        help="Web server HTTP port (default: 8080 or $PORT)")
    parser.add_argument("--host", dest="host",
                        default=os.environ.get("HOST", "0.0.0.0"),
                        help="Web server bind host (default: 0.0.0.0 or $HOST)")
    parser.add_argument("--no-interactive", action="store_true",
                        help="Disable interactive terminal menu when selecting ADB devices")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Dynamic device resolution
    resolved_device = resolve_serial(
        cli_serial=args.serial,
        interactive=not args.no_interactive
    )
    switch_target_device(resolved_device)

    app = create_app()
    logger.info("Camera Stream Server starting on http://%s:%d", args.host, args.port)
    web.run_app(app, host=args.host, port=args.port, print=None)
