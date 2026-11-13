import os
import sys
import json
import asyncio
import logging
from aiohttp import web

from camera_controller import DeviceCameraController
from stream_service import CameraStreamManager

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(name)s: %(message)s'
)
logger = logging.getLogger("server")

SERIAL = os.environ.get("ADB_SERIAL", "172.17.131.136:38163")
PORT = int(os.environ.get("PORT", "8080"))
HOST = os.environ.get("HOST", "0.0.0.0")

INDEX_HTML_PATH = os.path.join(os.path.dirname(__file__), "web", "index.html")

controller = DeviceCameraController(serial=SERIAL)
stream_mgr = CameraStreamManager(serial=SERIAL)

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
        "serial": SERIAL,
        "running": stream_mgr.running,
        "fps": round(stream_mgr.fps, 1),
        "has_frame": stream_mgr.latest_frame is not None
    }
    return web.json_response(data, headers={'Access-Control-Allow-Origin': '*'})

@routes.post('/api/switch_camera')
async def switch_camera_handler(request):
    controller.switch_camera()
    return web.json_response({"ok": True, "action": "switch_camera"})

@routes.post('/api/focus')
async def focus_handler(request):
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
    controller.trigger_shutter()
    return web.json_response({"ok": True, "action": "shutter"})

@routes.post('/api/wake')
async def wake_handler(request):
    controller.ensure_camera_active()
    return web.json_response({"ok": True, "action": "wake"})

async def on_startup(app):
    logger.info("Initializing camera on device %s...", SERIAL)
    controller.ensure_camera_active()
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

if __name__ == "__main__":
    app = create_app()
    logger.info("Camera Stream Server starting on http://%s:%d", HOST, PORT)
    web.run_app(app, host=HOST, port=PORT, print=None)
