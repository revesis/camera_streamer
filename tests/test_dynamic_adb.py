import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "camera_streamer"))

import adb_utils
import server
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop


class TestAdbUtils(unittest.TestCase):
    def test_parse_adb_devices(self):
        sample_output = (
            "List of devices attached\n"
            "172.17.131.136:37913   device product:realme_gt model:RMX3366 device:RMX3366 transport_id:1\n"
            "emulator-5554          offline transport_id:2\n"
        )
        with patch("adb_utils.run_adb_cmd", return_value=(0, sample_output, "")):
            devices = adb_utils.get_adb_devices()
            self.assertEqual(len(devices), 2)
            self.assertEqual(devices[0]["serial"], "172.17.131.136:37913")
            self.assertEqual(devices[0]["state"], "device")
            self.assertEqual(devices[0]["model"], "RMX3366")
            self.assertTrue(devices[0]["is_network"])

            self.assertEqual(devices[1]["serial"], "emulator-5554")
            self.assertEqual(devices[1]["state"], "offline")
            self.assertFalse(devices[1]["is_network"])

    def test_resolve_serial_priority_cli(self):
        # CLI priority should override ENV and auto-detect
        with patch.dict(os.environ, {"ADB_SERIAL": "env-serial:1234"}):
            with patch("adb_utils.connect_adb", return_value=(True, "connected")):
                res = adb_utils.resolve_serial(cli_serial="192.168.1.100:5555", interactive=False)
                self.assertEqual(res, "192.168.1.100:5555")

    def test_resolve_serial_priority_env(self):
        # ENV priority should override auto-detect when CLI is omitted
        with patch.dict(os.environ, {"ADB_SERIAL": "env-serial:5555"}):
            with patch("adb_utils.connect_adb", return_value=(True, "connected")):
                res = adb_utils.resolve_serial(cli_serial=None, interactive=False)
                self.assertEqual(res, "env-serial:5555")

    def test_resolve_serial_autodetect_single(self):
        # Auto-detect single device when no CLI or ENV provided
        with patch.dict(os.environ, {}, clear=True):
            with patch("adb_utils.get_adb_devices", return_value=[
                {"serial": "172.17.131.136:42000", "state": "device", "model": "Realme"}
            ]):
                res = adb_utils.resolve_serial(cli_serial=None, interactive=False)
                self.assertEqual(res, "172.17.131.136:42000")

    def test_resolve_serial_standby_on_empty(self):
        # Return None when no devices available and non-interactive
        with patch.dict(os.environ, {}, clear=True):
            with patch("adb_utils.get_adb_devices", return_value=[]):
                res = adb_utils.resolve_serial(cli_serial=None, interactive=False)
                self.assertIsNone(res)


class TestServerEndpoints(AioHTTPTestCase):
    async def get_application(self):
        server.switch_target_device("172.17.131.136:37913")
        return server.create_app()

    @unittest_run_loop
    async def test_status_endpoint(self):
        resp = await self.client.get('/api/status')
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data["serial"], "172.17.131.136:37913")
        self.assertTrue(data["connected"])

    @unittest_run_loop
    async def test_devices_endpoint(self):
        with patch("server.get_adb_devices", return_value=[{"serial": "dummy:1234", "state": "device"}]):
            resp = await self.client.get('/api/devices')
            self.assertEqual(resp.status, 200)
            data = await resp.json()
            self.assertEqual(data["current_serial"], "172.17.131.136:37913")
            self.assertEqual(len(data["devices"]), 1)

    @unittest_run_loop
    async def test_connect_and_disconnect(self):
        with patch("server.connect_adb", return_value=(True, "connected")):
            # Connect to new device
            resp = await self.client.post('/api/connect', json={"serial": "192.168.0.50:5555"})
            self.assertEqual(resp.status, 200)
            data = await resp.json()
            self.assertTrue(data["ok"])
            self.assertEqual(data["serial"], "192.168.0.50:5555")

            # Check status reflects update
            status_resp = await self.client.get('/api/status')
            status_data = await status_resp.json()
            self.assertEqual(status_data["serial"], "192.168.0.50:5555")

            # Disconnect
            with patch("server.disconnect_adb", return_value=(True, "disconnected")):
                disc_resp = await self.client.post('/api/disconnect')
                self.assertEqual(disc_resp.status, 200)
                status_resp2 = await self.client.get('/api/status')
                status_data2 = await status_resp2.json()
                self.assertIsNone(status_data2["serial"])
                self.assertFalse(status_data2["connected"])

    @unittest_run_loop
    async def test_screen_power_endpoint(self):
        # Test toggling screen power
        resp = await self.client.post('/api/screen_power', json={"action": "off"})
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["screen_off"])

        resp2 = await self.client.post('/api/screen_power', json={"action": "on"})
        self.assertEqual(resp2.status, 200)
        data2 = await resp2.json()
        self.assertTrue(data2["ok"])
        self.assertFalse(data2["screen_off"])


if __name__ == "__main__":
    unittest.main()
