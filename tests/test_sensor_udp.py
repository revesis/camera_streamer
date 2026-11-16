#!/usr/bin/env python3
import asyncio
import socket
import time
import unittest

from camera_streamer.proto import sensor_packet_pb2
from camera_streamer.sensor_udp_receiver import SensorUdpReceiver


class TestSensorUdpReceiver(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.received_packets = []
        self.port = 19999
        self.receiver = SensorUdpReceiver(
            host="127.0.0.1",
            port=self.port,
            on_packet=lambda pkt, addr: self.received_packets.append(pkt)
        )
        await self.receiver.start()

    async def asyncTearDown(self):
        self.receiver.stop()

    async def test_protobuf_udp_transmission_and_stats(self):
        # Create a client UDP socket
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        target = ("127.0.0.1", self.port)

        total_to_send = 50
        for i in range(total_to_send):
            packet = sensor_packet_pb2.SensorPacket()
            packet.sequence_number = i + 1
            packet.timestamp_ns = time.time_ns()
            packet.device_id = "realme-test-device"

            # Populate modular IMU
            packet.imu.accel.x = 0.12 * i
            packet.imu.accel.y = -9.81
            packet.imu.accel.z = 0.05
            packet.imu.gyro.x = 0.01
            packet.imu.gyro.y = 0.02
            packet.imu.gyro.z = -0.03

            # Populate modular Orientation
            packet.orientation.rotation_vector.w = 0.99
            packet.orientation.rotation_vector.x = 0.05
            packet.orientation.rotation_vector.y = 0.01
            packet.orientation.rotation_vector.z = 0.02
            packet.orientation.rotation_vector.accuracy = 0.95

            payload = packet.SerializeToString()
            client_sock.sendto(payload, target)
            await asyncio.sleep(0.002)  # ~500 Hz simulation

        # Wait for all packets to be processed
        await asyncio.sleep(0.1)

        self.assertEqual(len(self.received_packets), total_to_send)
        first_pkt = self.received_packets[0]
        self.assertEqual(first_pkt.sequence_number, 1)
        self.assertEqual(first_pkt.device_id, "realme-test-device")
        self.assertAlmostEqual(first_pkt.imu.accel.y, -9.81, places=2)
        self.assertAlmostEqual(first_pkt.orientation.rotation_vector.w, 0.99, places=2)

        last_pkt = self.received_packets[-1]
        self.assertEqual(last_pkt.sequence_number, total_to_send)

        stats = self.receiver.stats
        self.assertIsNotNone(stats)
        self.assertEqual(stats.total_packets, total_to_send)
        self.assertEqual(stats.lost_packets, 0)
        self.assertEqual(stats.loss_rate_percent, 0.0)

        client_sock.close()


if __name__ == "__main__":
    unittest.main()
