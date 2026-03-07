"""Screen recording and GIF capture for BazzCap.

Supports:
  - Video recording via FFmpeg + PipeWire (Wayland) or x11grab (X11)
  - XDG Desktop Portal for source selection on Wayland
  - GIF conversion via FFmpeg
"""

import subprocess
import shutil
import os
import signal
import time
import threading
from enum import Enum, auto


class RecordingState(Enum):
    IDLE = auto()
    RECORDING = auto()
    CONVERTING = auto()


class ScreenRecorder:
    """Screen recorder using FFmpeg with PipeWire (Wayland) or x11grab (X11)."""

    def __init__(self, config):
        self._config = config
        self._state = RecordingState.IDLE
        self._process = None
        self._output_path = None
        self._start_time = 0
        self._pipewire_node = None
        self._on_state_change = None
        self._on_error = None
        self._on_complete = None

    @property
    def state(self):
        return self._state

    @property
    def is_recording(self):
        return self._state == RecordingState.RECORDING

    @property
    def elapsed(self):
        if self._state == RecordingState.RECORDING:
            return time.time() - self._start_time
        return 0

    def set_callbacks(self, on_state_change=None, on_error=None, on_complete=None):
        """Set callback functions."""
        self._on_state_change = on_state_change
        self._on_error = on_error
        self._on_complete = on_complete

    def _notify_state(self):
        if self._on_state_change:
            self._on_state_change(self._state)

    def _notify_error(self, msg):
        if self._on_error:
            self._on_error(msg)

    def _notify_complete(self, path):
        if self._on_complete:
            self._on_complete(path)

    def _is_wayland(self):
        return os.environ.get("WAYLAND_DISPLAY") or \
               os.environ.get("XDG_SESSION_TYPE") == "wayland"

    def _has(self, cmd):
        return shutil.which(cmd) is not None

    def start_recording(self, output_path: str, use_audio: bool = False) -> bool:
        """Start screen recording.

        On Wayland: uses XDG portal to select source, then FFmpeg with PipeWire.
        On X11: uses FFmpeg with x11grab.
        Returns True if recording started successfully.
        """
        if self._state != RecordingState.IDLE:
            return False

        if not self._has("ffmpeg"):
            self._notify_error("FFmpeg not found. Install it with: "
                               "rpm-ostree install ffmpeg (or flatpak)")
            return False

        self._output_path = output_path
        fps = self._config.get("recording_fps", 30)

        if self._is_wayland():
            return self._start_wayland_recording(output_path, fps, use_audio)
        else:
            return self._start_x11_recording(output_path, fps, use_audio)

    def _start_wayland_recording(self, output_path, fps, use_audio):
        """Start recording on Wayland via XDG Portal + PipeWire."""
        # Step 1: Get PipeWire node via portal
        helper = os.path.join(os.path.dirname(__file__), "_portal_helper.py")
        if not os.path.exists(helper):
            self._notify_error("Portal helper not found")
            return False

        try:
            r = subprocess.run(
                ["python3", helper, "screencast", "--start"],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode != 0:
                # Fallback: try wf-recorder
                return self._start_wfrecorder(output_path, fps, use_audio)

            lines = r.stdout.strip().split("\n")
            self._pipewire_node = lines[0] if lines else None
            if not self._pipewire_node:
                self._notify_error("Could not get PipeWire node from portal")
                return False

        except (subprocess.SubprocessError, OSError) as e:
            self._notify_error(f"Portal screencast failed: {e}")
            return False

        # Step 2: Record from PipeWire node
        cmd = [
            "ffmpeg", "-y",
            "-f", "pipewire",
            "-i", self._pipewire_node,
            "-r", str(fps),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
        ]

        if use_audio:
            cmd.extend(["-c:a", "aac"])

        cmd.append(output_path)
        return self._launch_ffmpeg(cmd)

    def _start_wfrecorder(self, output_path, fps, use_audio):
        """Fallback: use wf-recorder if available (wlroots compositors)."""
        if not self._has("wf-recorder"):
            self._notify_error("No recording method available for Wayland. "
                               "Install wf-recorder or ensure PipeWire portal works.")
            return False

        cmd = ["wf-recorder", "-f", output_path, "--fps", str(fps)]
        if use_audio:
            cmd.extend(["-a"])

        try:
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            self._state = RecordingState.RECORDING
            self._start_time = time.time()
            self._notify_state()
            return True
        except (OSError, subprocess.SubprocessError) as e:
            self._notify_error(f"wf-recorder failed: {e}")
            return False

    def _start_x11_recording(self, output_path, fps, use_audio):
        """Start recording on X11 via FFmpeg x11grab."""
        display = os.environ.get("DISPLAY", ":0")

        # Get screen size
        try:
            r = subprocess.run(
                ["xdpyinfo"],
                capture_output=True, text=True, timeout=5,
            )
            # Parse dimensions from xdpyinfo
            size = "1920x1080"  # default
            for line in r.stdout.split("\n"):
                if "dimensions:" in line:
                    parts = line.split()
                    for p in parts:
                        if "x" in p and p[0].isdigit():
                            size = p
                            break
                    break
        except (subprocess.SubprocessError, OSError):
            size = "1920x1080"

        cmd = [
            "ffmpeg", "-y",
            "-f", "x11grab",
            "-framerate", str(fps),
            "-video_size", size,
            "-i", display,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
        ]

        if use_audio and self._has("pactl"):
            cmd = [
                "ffmpeg", "-y",
                "-f", "x11grab",
                "-framerate", str(fps),
                "-video_size", size,
                "-i", display,
                "-f", "pulse",
                "-i", "default",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "23",
                "-c:a", "aac",
            ]

        cmd.append(output_path)
        return self._launch_ffmpeg(cmd)

    def _launch_ffmpeg(self, cmd):
        """Start FFmpeg process."""
        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self._state = RecordingState.RECORDING
            self._start_time = time.time()
            self._notify_state()
            return True
        except (OSError, subprocess.SubprocessError) as e:
            self._notify_error(f"FFmpeg failed to start: {e}")
            return False

    def stop_recording(self) -> str | None:
        """Stop the current recording.

        Returns the output file path on success, None on failure.
        """
        if self._state != RecordingState.RECORDING or not self._process:
            return None

        try:
            # Send 'q' to FFmpeg stdin for graceful stop
            if self._process.stdin:
                self._process.stdin.write(b"q")
                self._process.stdin.flush()
                self._process.stdin.close()

            # Wait for process to finish
            self._process.wait(timeout=10)

        except (subprocess.TimeoutExpired, OSError, BrokenPipeError):
            try:
                self._process.send_signal(signal.SIGINT)
                self._process.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                self._process.kill()

        self._process = None
        self._state = RecordingState.IDLE
        self._notify_state()

        if self._output_path and os.path.isfile(self._output_path):
            self._notify_complete(self._output_path)
            return self._output_path

        return None

    def convert_to_gif(self, video_path: str, gif_path: str = None,
                       callback=None) -> None:
        """Convert a video recording to GIF. Runs in a background thread.

        Uses FFmpeg's palettegen for high-quality GIF output.
        """
        if not self._has("ffmpeg"):
            if callback:
                callback(None, "FFmpeg not found")
            return

        if not gif_path:
            gif_path = os.path.splitext(video_path)[0] + ".gif"

        gif_fps = self._config.get("gif_fps", 15)
        max_width = self._config.get("gif_max_width", 640)

        def _convert():
            self._state = RecordingState.CONVERTING
            self._notify_state()

            try:
                # Two-pass GIF with palette for quality
                palette = video_path + "_palette.png"

                # Pass 1: Generate palette
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", video_path,
                        "-vf", f"fps={gif_fps},scale={max_width}:-1:flags=lanczos,palettegen",
                        palette,
                    ],
                    capture_output=True, timeout=300, check=True,
                )

                # Pass 2: Generate GIF with palette
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", video_path, "-i", palette,
                        "-lavfi", f"fps={gif_fps},scale={max_width}:-1:flags=lanczos[x];[x][1:v]paletteuse",
                        gif_path,
                    ],
                    capture_output=True, timeout=300, check=True,
                )

                # Clean up palette
                try:
                    os.unlink(palette)
                except OSError:
                    pass

                self._state = RecordingState.IDLE
                self._notify_state()

                if os.path.isfile(gif_path):
                    if callback:
                        callback(gif_path, None)
                else:
                    if callback:
                        callback(None, "GIF conversion produced no output")

            except subprocess.CalledProcessError as e:
                self._state = RecordingState.IDLE
                self._notify_state()
                if callback:
                    callback(None, f"GIF conversion failed: {e.stderr}")
            except subprocess.TimeoutExpired:
                self._state = RecordingState.IDLE
                self._notify_state()
                if callback:
                    callback(None, "GIF conversion timed out")

        thread = threading.Thread(target=_convert, daemon=True)
        thread.start()
