#!/usr/bin/env python3
"""
Sensor UDP Receiver for Android Sensor Agent.
Listens for Protobuf over UDP packets, parses sensor data,
tracks sequence drops, and monitors streaming rates in real-time.
"""

import asyncio
import logging
import time
from typing import Callable, Optional, Tuple

from camera_streamer.proto import sensor_packet_pb2

logger = logging.getLogger("SensorUdpReceiver")


class SensorReceiverStats:
    """Statistics tracker for UDP sensor streaming."""

    def __init__(self, window_size_seconds: float = 1.0):
        self.window_size = window_size_seconds
        self.total_packets: int = 0
        self.total_bytes: int = 0
        self.lost_packets: int = 0
        self.last_seq: Optional[int] = None

        # Sliding window metrics
        self.window_start = time.time()
        self.window_packets: int = 0
        self.window_bytes: int = 0
        self.current_fps: float = 0.0
        self.current_kbps: float = 0.0

    def update(self, seq: int, byte_length: int) -> None:
        now = time.time()
        self.total_packets += 1
        self.total_bytes += byte_length
        self.window_packets += 1
        self.window_bytes += byte_length

        if self.last_seq is not None:
            if seq > self.last_seq + 1:
                dropped = (seq - self.last_seq - 1)
                self.lost_packets += dropped
        self.last_seq = seq

        elapsed = now - self.window_start
        if elapsed >= self.window_size:
            self.current_fps = self.window_packets / elapsed
            self.current_kbps = (self.window_bytes / 1024.0) / elapsed
            self.window_start = now
            self.window_packets = 0
            self.window_bytes = 0

    @property
    def loss_rate_percent(self) -> float:
        total = self.total_packets + self.lost_packets
        if total == 0:
            return 0.0
        return (self.lost_packets / total) * 100.0


class SensorDatagramProtocol(asyncio.DatagramProtocol):
    """Asyncio Datagram Protocol to receive and deserialize SensorPacket protobufs."""

    def __init__(self, on_packet: Optional[Callable[[sensor_packet_pb2.SensorPacket, Tuple[str, int]], None]] = None):
        self.on_packet = on_packet
        self.stats = SensorReceiverStats()
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.last_sender_addr: Optional[Tuple[str, int]] = None

    def connection_made(self, transport: asyncio.DatagramTransport):  # type: ignore
        self.transport = transport
        logger.info("UDP Sensor Receiver socket bound and listening.")

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        try:
            self.last_sender_addr = addr
            packet = sensor_packet_pb2.SensorPacket()
            packet.ParseFromString(data)
            self.stats.update(packet.sequence_number, len(data))

            if self.on_packet:
                self.on_packet(packet, addr)
        except Exception as e:
            logger.warning("Failed to deserialize sensor packet from %s: %s", addr, e)

    def error_received(self, exc: Exception):
        logger.error("UDP socket error received: %s", exc)

    def connection_lost(self, exc: Optional[Exception]):
        if exc:
            logger.warning("UDP socket closed with error: %s", exc)
        else:
            logger.info("UDP socket closed.")


class SensorUdpReceiver:
    """Manages the lifecycle of the Asyncio UDP Sensor Receiver."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9999,
        on_packet: Optional[Callable[[sensor_packet_pb2.SensorPacket, Tuple[str, int]], None]] = None
    ):
        self.host = host
        self.port = port
        self.on_packet = on_packet
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.protocol: Optional[SensorDatagramProtocol] = None

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: SensorDatagramProtocol(self.on_packet),
            local_addr=(self.host, self.port)
        )
        logger.info(f"Sensor UDP Receiver successfully started on {self.host}:{self.port}")

    def stop(self) -> None:
        if self.transport:
            self.transport.close()
            self.transport = None
            self.protocol = None
            logger.info("Sensor UDP Receiver stopped.")

    @property
    def stats(self) -> Optional[SensorReceiverStats]:
        return self.protocol.stats if self.protocol else None

    @property
    def last_sender_addr(self) -> Optional[Tuple[str, int]]:
        return getattr(self.protocol, "last_sender_addr", None) if self.protocol else None

    def send(self, data: bytes, addr: Optional[Tuple[str, int]] = None) -> bool:
        target_addr = addr or self.last_sender_addr
        if not target_addr:
            logger.warning("Cannot send UDP packet: target address unknown.")
            return False
        if not self.transport:
            logger.warning("Cannot send UDP packet: transport not connected.")
            return False
        try:
            self.transport.sendto(data, target_addr)
            return True
        except Exception as e:
            logger.error("Error sending UDP datagram to %s: %s", target_addr, e)
            return False


class FrameAssembler:
    """Assembles UDP-chunked JPEG frames."""

    def __init__(self):
        self.frames = {}

    def add_chunk(self, frame_id: int, chunk_idx: int, total_chunks: int, payload: bytes) -> Optional[bytes]:
        if total_chunks <= 1:
            return payload

        if frame_id not in self.frames:
            self.frames[frame_id] = {"total": total_chunks, "chunks": {}}
        
        entry = self.frames[frame_id]
        entry["chunks"][chunk_idx] = payload

        if len(entry["chunks"]) == total_chunks:
            full_frame = b"".join(entry["chunks"][i] for i in range(total_chunks) if i in entry["chunks"])
            del self.frames[frame_id]
            # Prune old incomplete frames
            if len(self.frames) > 10:
                old_ids = sorted(self.frames.keys())[:-10]
                for oid in old_ids:
                    del self.frames[oid]
            return full_frame
        return None


frame_assembler = FrameAssembler()


async def _run_cli_server(host: str, port: int, verbose: bool):
    def handle_packet(pkt: sensor_packet_pb2.SensorPacket, addr: Tuple[str, int]):
        if verbose:
            parts = [f"Seq={pkt.sequence_number}", f"Dev={pkt.device_id}"]
            if pkt.HasField("imu"):
                acc = pkt.imu.accel
                gyro = pkt.imu.gyro
                parts.append(f"Acc=({acc.x:.2f},{acc.y:.2f},{acc.z:.2f})")
                parts.append(f"Gyro=({gyro.x:.2f},{gyro.y:.2f},{gyro.z:.2f})")
            if pkt.HasField("orientation"):
                q = pkt.orientation.rotation_vector
                parts.append(f"Quat=({q.w:.2f},{q.x:.2f},{q.y:.2f},{q.z:.2f})")
            if pkt.HasField("camera_frame"):
                cf = pkt.camera_frame
                assembled = frame_assembler.add_chunk(cf.frame_id, cf.chunk_index, cf.total_chunks, cf.payload)
                if assembled:
                    parts.append(f"CamFrame[Reassembled]={cf.width}x{cf.height} ({len(assembled)}B)")
                    try:
                        with open("/tmp/latest_camera_frame.jpg", "wb") as f:
                            f.write(assembled)
                    except Exception:
                        pass
                else:
                    parts.append(f"CamChunk={cf.chunk_index+1}/{cf.total_chunks} (FId={cf.frame_id})")
            print(f"[{addr[0]}:{addr[1]}] " + " | ".join(parts), flush=True)

    receiver = SensorUdpReceiver(host=host, port=port, on_packet=handle_packet)
    await receiver.start()
    print(f"🚀 Sensor UDP Receiver running on {host}:{port}. Press Ctrl+C to stop.", flush=True)

    try:
        while True:
            await asyncio.sleep(1.0)
            stats = receiver.stats
            if stats and stats.total_packets > 0:
                print(
                    f"[Stats] Rate: {stats.current_fps:.1f} Hz | "
                    f"Throughput: {stats.current_kbps:.1f} KB/s | "
                    f"Total: {stats.total_packets} pkts | "
                    f"Lost: {stats.lost_packets} ({stats.loss_rate_percent:.2f}%)",
                    flush=True
                )
    except asyncio.CancelledError:
        pass
    finally:
        receiver.stop()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Android Sensor Protobuf-over-UDP Receiver")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address to bind (default: 0.0.0.0)")
    parser.add_argument("-p", "--port", type=int, default=9999, help="UDP port (default: 9999)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print details of each received packet")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        asyncio.run(_run_cli_server(args.host, args.port, args.verbose))
    except KeyboardInterrupt:
        print("\nShutdown requested by user.")


if __name__ == "__main__":
    main()
