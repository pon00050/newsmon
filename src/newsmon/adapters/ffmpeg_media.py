"""Footage inspection with the local ffmpeg/ffprobe binaries (duty 2, v1).

Decoding and filtering a file is I/O under the owner's compute policy: no model runs here. Filters and thresholds are the
ones calibrated with known-answer and nonsense controls in `03_experiments/multimedia` (R8). Every call has a timeout;
callers record a failure instead of raising through the collection cycle.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

BLACK = "blackdetect=d=1:pic_th=0.98:pix_th=0.10"
FREEZE = "freezedetect=n=-60dB:d=2"
SILENCE = "silencedetect=n=-50dB:d=1"
TIMEOUT_S = 120

_BLACK_RX = re.compile(r"black_start:(?P<s>-?[\d.]+)\s+black_end:(?P<e>[\d.]+)")
_FREEZE_S = re.compile(r"lavfi\.freezedetect\.freeze_start: (?P<v>[\d.]+)")
_FREEZE_E = re.compile(r"lavfi\.freezedetect\.freeze_end: (?P<v>[\d.]+)")
_SIL_S = re.compile(r"silence_start: (?P<v>-?[\d.]+)")
_SIL_E = re.compile(r"silence_end: (?P<v>[\d.]+)")


class MediaToolError(RuntimeError):
    pass


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        raise MediaToolError(f"timed out after {TIMEOUT_S} s") from None


def _last_line(text: str | None, default: str) -> str:
    lines = [x for x in (text or "").strip().splitlines() if x.strip()]
    return (lines[-1] if lines else default)[:300]


def _pairs(starts: list[float], ends: list[float], duration: float | None) -> list[tuple[float, float]]:
    out = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else duration  # an event still running at the end of the file
        if e is not None:
            out.append((round(max(0.0, s), 2), round(e, 2)))
    return out


class FfmpegMedia:
    def __init__(self, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> None:
        self.ffmpeg, self.ffprobe = ffmpeg, ffprobe

    @classmethod
    def available(cls) -> "FfmpegMedia | None":
        return cls() if shutil.which("ffprobe") and shutil.which("ffmpeg") else None

    def probe(self, path: Path) -> dict:
        r = _run([self.ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
        if r.returncode != 0:
            raise MediaToolError(_last_line(r.stderr, "ffprobe failed"))
        data = json.loads(r.stdout or "{}")
        fmt = data.get("format") or {}
        v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
        a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
        if v is None and a is None:
            raise MediaToolError("no audio or video stream")

        def num(x):
            try:
                return float(x)
            except (TypeError, ValueError):
                return None

        fps = None
        if v and v.get("avg_frame_rate") and "/" in v["avg_frame_rate"]:
            n, d = v["avg_frame_rate"].split("/", 1)
            fps = round(float(n) / float(d), 2) if num(n) and num(d) else None
        return {"container": fmt.get("format_name"), "duration_s": num(fmt.get("duration")),
                "size_bytes": int(fmt["size"]) if str(fmt.get("size", "")).isdigit() else None,
                "video": {"codec": v.get("codec_name"), "width": v.get("width"), "height": v.get("height"), "fps": fps}
                if v else None,
                "audio": {"codec": a.get("codec_name"), "channels": a.get("channels"),
                          "sample_rate": int(a["sample_rate"]) if str(a.get("sample_rate", "")).isdigit() else None}
                if a else None}

    def detect(self, path: Path, *, has_video: bool, has_audio: bool, duration: float | None) -> dict:
        """Black, freeze and silence intervals in seconds. Freeze overlapping black is removed (a black picture is also
        static); freeze alone is reported as a note because graphics and slates are legitimately static."""
        cmd = [self.ffmpeg, "-hide_banner", "-nostats", "-i", str(path)]
        if has_video:
            cmd += ["-vf", f"{BLACK},{FREEZE},metadata=mode=print"]
        if has_audio:
            cmd += ["-af", SILENCE]
        cmd += ["-f", "null", "-"]
        r = _run(cmd)
        if r.returncode != 0:
            raise MediaToolError(_last_line(r.stderr, "ffmpeg failed"))
        err = r.stderr or ""
        black = [(round(max(0.0, float(m["s"])), 2), round(float(m["e"]), 2)) for m in _BLACK_RX.finditer(err)]
        freeze = _pairs([float(m["v"]) for m in _FREEZE_S.finditer(err)], [float(m["v"]) for m in _FREEZE_E.finditer(err)],
                        duration)
        silence = _pairs([float(m["v"]) for m in _SIL_S.finditer(err)], [float(m["v"]) for m in _SIL_E.finditer(err)],
                         duration)
        freeze = [f for f in freeze if not any(f[0] < b[1] and b[0] < f[1] for b in black)]
        return {"black": black, "silence": silence, "freeze": freeze}

    def thumbnail(self, path: Path, out: Path, duration: float | None) -> bool:
        """A 5-frame strip, 192 px wide per frame, spread over the clip."""
        step = max(1.0, (duration or 10.0) / 5)
        out.parent.mkdir(parents=True, exist_ok=True)
        r = _run([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), "-vf",
                  f"fps=1/{step:.3f},scale=192:-2,tile=5x1", "-frames:v", "1", "-update", "1", str(out)])
        return r.returncode == 0 and out.is_file()
