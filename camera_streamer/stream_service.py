import os
import time
import subprocess
import threading
import logging

logger = logging.getLogger("stream_service")

class CameraStreamManager:
    def __init__(self, serial="172.17.131.136:38163", v4l2_device="/dev/video0", max_fps=30, max_size=720):
        self.serial = serial
        self.v4l2_device = v4l2_device
        self.max_fps = max_fps
        self.max_size = max_size

        self.running = False
        self.scrcpy_proc = None
        self.ffmpeg_proc = None
        self.thread = None

        self.latest_frame = None
        self.frame_condition = threading.Condition()
        self.frame_id = 0
        self.fps = 0.0

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_pipeline, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self._terminate_subprocesses()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)

    def _terminate_subprocesses(self):
        for proc, name in [(self.ffmpeg_proc, "ffmpeg"), (self.scrcpy_proc, "scrcpy")]:
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=1.0)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        self.ffmpeg_proc = None
        self.scrcpy_proc = None

    def _run_pipeline(self):
        # Ensure v4l2loopback module is loaded
        try:
            subprocess.run(["modprobe", "v4l2loopback"], check=False)
        except Exception:
            pass

        while self.running:
            try:
                env = os.environ.copy()
                env["SDL_VIDEODRIVER"] = "dummy"

                scrcpy_cmd = [
                    "scrcpy", "-s", self.serial,
                    "--crop=1080:1440:0:216",
                    f"--max-size={self.max_size}",
                    f"--max-fps={self.max_fps}",
                    "--video-bit-rate=4M",
                    "--no-playback",
                    "--no-audio",
                    f"--v4l2-sink={self.v4l2_device}"
                ]
                logger.info("Starting scrcpy (V4L2 kernel sink): %s", " ".join(scrcpy_cmd))
                self.scrcpy_proc = subprocess.Popen(
                    scrcpy_cmd,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

                # Wait for scrcpy to initialize v4l2 device
                time.sleep(1.8)

                ffmpeg_cmd = [
                    "ffmpeg", "-y",
                    "-f", "v4l2",
                    "-thread_queue_size", "1",
                    "-fflags", "nobuffer",
                    "-flags", "low_delay",
                    "-i", self.v4l2_device,
                    "-f", "image2pipe",
                    "-vcodec", "mjpeg",
                    "-q:v", "5",
                    "-"
                ]
                logger.info("Starting ffmpeg (zero-delay V4L2 reader): %s", " ".join(ffmpeg_cmd))
                self.ffmpeg_proc = subprocess.Popen(
                    ffmpeg_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL
                )

                buf = bytearray()
                frame_count = 0
                last_fps_time = time.time()

                while self.running:
                    chunk = self.ffmpeg_proc.stdout.read(8192)
                    if not chunk:
                        logger.warning("FFmpeg stdout closed.")
                        break
                    buf.extend(chunk)

                    while True:
                        soi = buf.find(b'\xff\xd8')
                        if soi == -1:
                            buf.clear()
                            break
                        eoi = buf.find(b'\xff\xd9', soi)
                        if eoi == -1:
                            if soi > 0:
                                del buf[:soi]
                            break

                        frame = bytes(buf[soi:eoi + 2])
                        del buf[:eoi + 2]

                        frame_count += 1
                        now = time.time()
                        if now - last_fps_time >= 1.0:
                            self.fps = frame_count / (now - last_fps_time)
                            frame_count = 0
                            last_fps_time = now

                        with self.frame_condition:
                            self.latest_frame = frame
                            self.frame_id += 1
                            self.frame_condition.notify_all()

            except Exception as e:
                logger.error("Error in camera pipeline loop: %s", e)
            finally:
                self._terminate_subprocesses()

            if self.running:
                logger.info("Pipeline disconnected. Restarting in 1.5 seconds...")
                time.sleep(1.5)

    def get_latest_frame(self):
        with self.frame_condition:
            return self.latest_frame
