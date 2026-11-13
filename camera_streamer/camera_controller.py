import subprocess
import time
import threading
import logging

logger = logging.getLogger("camera_controller")

class DeviceCameraController:
    def __init__(self, serial="172.17.131.136:38163"):
        self.serial = serial
        # Viewfinder bounds: [0, 216] to [1080, 1656] (width: 1080, height: 1440)
        self.vf_left = 0
        self.vf_top = 216
        self.vf_width = 1080
        self.vf_height = 1440

        # Controls coordinates
        self.shutter_x = 540
        self.shutter_y = 2019
        self.switch_x = 882
        self.switch_y = 2019

        self._watchdog_running = False
        self._watchdog_thread = None

    def _adb(self, *args, timeout=8):
        cmd = ["adb", "-s", self.serial] + list(args)
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
            return res.stdout.strip()
        except Exception as e:
            logger.error("ADB command %s failed: %s", cmd, e)
            return ""

    def ensure_camera_active(self):
        """Wake up device, dismiss keyguard, keep awake, and ensure camera activity is in foreground"""
        logger.info("Ensuring camera is active on device %s...", self.serial)
        self._adb("shell", "svc power stayon true; input keyevent 224; am start -a android.media.action.STILL_IMAGE_CAMERA")
        return True

    def switch_camera(self):
        """Switch between rear and front cameras"""
        logger.info("Switching camera...")
        self._adb("shell", f"input tap {self.switch_x} {self.switch_y}")

    def tap_focus(self, rel_x=0.5, rel_y=0.5):
        """Focus on a relative position (0.0 to 1.0) in the viewfinder"""
        rel_x = max(0.05, min(0.95, float(rel_x)))
        rel_y = max(0.05, min(0.95, float(rel_y)))
        abs_x = int(self.vf_left + rel_x * self.vf_width)
        abs_y = int(self.vf_top + rel_y * self.vf_height)
        logger.info("Tapping focus at relative (%.2f, %.2f) -> screen (%d, %d)", rel_x, rel_y, abs_x, abs_y)
        self._adb("shell", f"input tap {abs_x} {abs_y}")

    def trigger_shutter(self):
        """Trigger physical shutter on phone"""
        logger.info("Triggering phone shutter...")
        self._adb("shell", f"input tap {self.shutter_x} {self.shutter_y}")

    def start_watchdog(self):
        """Background thread that monitors camera focus and relaunches if closed/timed out"""
        if self._watchdog_running:
            return
        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()

    def stop_watchdog(self):
        self._watchdog_running = False

    def _watchdog_loop(self):
        while self._watchdog_running:
            time.sleep(6)
            try:
                focus = self._adb("shell", "dumpsys window | grep mCurrentFocus", timeout=5)
                if focus and "com.oppo.camera" not in focus:
                    logger.warning("Camera lost focus (%s). Auto-relaunching camera...", focus)
                    self.ensure_camera_active()
            except Exception:
                pass
