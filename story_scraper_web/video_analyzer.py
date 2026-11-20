"""
Facebook Video Analyzer
=======================
Downloads a public Facebook video with yt-dlp, uploads it to the Gemini
Files API and asks a Gemini model to analyse it with a (long) instruction.

Configuration (environment variables):
    GEMINI_API_KEY        required - Google AI Studio key
    GEMINI_MODEL          optional - default "gemini-2.5-flash"
    VIDEO_MAX_MB          optional - reject downloads above this size (default 200)
    VIDEO_MAX_SECONDS     optional - reject videos longer than this (default 1800)
    VIDEO_TMP_DIR         optional - where downloads land (default <this dir>/tmp_videos)
"""
import os
import re
import sys
import time
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Callable, Optional

BASE_DIR = Path(__file__).resolve().parent
PROMPT_FILE = BASE_DIR / "prompts" / "video_instruction.txt"

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
MAX_MB = int(os.environ.get("VIDEO_MAX_MB", "200"))
MAX_SECONDS = int(os.environ.get("VIDEO_MAX_SECONDS", "1800"))
TMP_DIR = Path(os.environ.get("VIDEO_TMP_DIR", BASE_DIR / "tmp_videos"))

FB_URL_RE = re.compile(
    r"^https?://(?:[\w-]+\.)?(?:facebook\.com|fb\.watch|fb\.com)/", re.I
)


class VideoAnalyzerError(Exception):
    """User-facing error (message is safe to show in the UI)."""


def load_default_instruction() -> str:
    try:
        return PROMPT_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _log(cb: Optional[Callable[[str], None]], msg: str) -> None:
    if cb:
        cb(msg)


def is_facebook_url(url: str) -> bool:
    return bool(FB_URL_RE.match(url.strip()))


def _yt_dlp_cmd() -> list:
    """Prefer the yt-dlp installed next to the running interpreter."""
    exe = Path(sys.executable).parent / ("yt-dlp.exe" if os.name == "nt" else "yt-dlp")
    if exe.exists():
        return [str(exe)]
    if shutil.which("yt-dlp"):
        return ["yt-dlp"]
    return [sys.executable, "-m", "yt_dlp"]


def download_facebook_video(url: str, status_callback=None) -> Path:
    """Downloads the video to a fresh temp dir and returns the mp4 path."""
    url = url.strip()
    if not is_facebook_url(url):
        raise VideoAnalyzerError("Link không phải Facebook (facebook.com / fb.watch).")

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="fbvid_", dir=TMP_DIR))
    out_tmpl = str(work_dir / "video.%(ext)s")

    cmd = _yt_dlp_cmd() + [
        "--no-playlist",
        "--no-warnings",
        "--max-filesize", f"{MAX_MB}m",
        "--match-filter", f"duration <= {MAX_SECONDS}",
        # smallest reasonable mp4 so uploads stay quick on a small VPS
        "-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/b[ext=mp4]/b",
        "--merge-output-format", "mp4",
        "-o", out_tmpl,
        url,
    ]
    _log(status_callback, "⬇️ Đang tải video từ Facebook...")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise VideoAnalyzerError("Tải video quá 10 phút, đã huỷ.")

    files = sorted(work_dir.glob("video.*"))
    if proc.returncode != 0 or not files:
        shutil.rmtree(work_dir, ignore_errors=True)
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = err[-1] if err else "không rõ nguyên nhân"
        if "login" in tail.lower() or "private" in tail.lower() or "cookies" in tail.lower():
            raise VideoAnalyzerError("Video riêng tư hoặc cần đăng nhập Facebook. Chỉ hỗ trợ video công khai.")
        if "filesize" in tail.lower() or "does not pass filter" in tail.lower():
            raise VideoAnalyzerError(f"Video vượt giới hạn ({MAX_MB} MB / {MAX_SECONDS // 60} phút).")
        raise VideoAnalyzerError(f"Không tải được video: {tail}")

    video = files[0]
    size_mb = video.stat().st_size / (1024 * 1024)
    _log(status_callback, f"✅ Đã tải xong ({size_mb:.1f} MB).")
    return video


def _get_client():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise VideoAnalyzerError("Thiếu GEMINI_API_KEY trên server. Liên hệ quản trị viên.")
    try:
        from google import genai
    except ImportError:
        raise VideoAnalyzerError("Chưa cài thư viện google-genai trên server.")
    return genai.Client(api_key=api_key)


def analyze_video_file(video_path: Path, instruction: str, model: str = None,
                       status_callback=None) -> dict:
    """Uploads the file to Gemini, waits until ACTIVE, runs the instruction."""
    from google.genai import types

    model = model or DEFAULT_MODEL
    client = _get_client()

    _log(status_callback, "☁️ Đang upload video lên Gemini...")
    uploaded = client.files.upload(
        file=str(video_path),
        config=types.UploadFileConfig(mime_type="video/mp4", display_name=video_path.name),
    )
    try:
        _log(status_callback, "⏳ Gemini đang xử lý video...")
        deadline = time.time() + 600
        while uploaded.state and uploaded.state.name == "PROCESSING":
            if time.time() > deadline:
                raise VideoAnalyzerError("Gemini xử lý video quá 10 phút, đã huỷ.")
            time.sleep(3)
            uploaded = client.files.get(name=uploaded.name)
        if uploaded.state and uploaded.state.name == "FAILED":
            msg = getattr(uploaded.error, "message", "") if uploaded.error else ""
            raise VideoAnalyzerError(f"Gemini không xử lý được video. {msg}".strip())

        _log(status_callback, f"🤖 Đang gọi model {model}...")
        t0 = time.time()
        response = client.models.generate_content(
            model=model,
            contents=[uploaded, instruction],
            config=types.GenerateContentConfig(temperature=0.4),
        )
        elapsed = time.time() - t0
        text = (response.text or "").strip()
        if not text:
            raise VideoAnalyzerError("Model trả về rỗng (có thể bị chặn bởi safety filter).")

        usage = getattr(response, "usage_metadata", None)
        return {
            "text": text,
            "model": model,
            "elapsed_s": round(elapsed, 1),
            "prompt_tokens": getattr(usage, "prompt_token_count", None),
            "output_tokens": getattr(usage, "candidates_token_count", None),
        }
    finally:
        try:
            client.files.delete(name=uploaded.name)
        except Exception:
            pass


def analyze_facebook_video(url: str, instruction: str, model: str = None,
                           status_callback=None) -> dict:
    """End-to-end: download -> upload -> analyse -> cleanup."""
    instruction = (instruction or "").strip()
    if not instruction:
        raise VideoAnalyzerError("Instruction đang trống.")
    video = download_facebook_video(url, status_callback)
    try:
        result = analyze_video_file(video, instruction, model, status_callback)
        result["url"] = url.strip()
        result["video_size_mb"] = round(video.stat().st_size / (1024 * 1024), 1)
        return result
    finally:
        shutil.rmtree(video.parent, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python video_analyzer.py <facebook_video_url> [instruction_file]")
        sys.exit(1)
    instr = Path(sys.argv[2]).read_text(encoding="utf-8") if len(sys.argv) > 2 else load_default_instruction()
    res = analyze_facebook_video(sys.argv[1], instr, status_callback=print)
    print("=" * 60)
    print(res["text"])
    print("=" * 60)
    print(f"model={res['model']} elapsed={res['elapsed_s']}s tokens={res['prompt_tokens']}/{res['output_tokens']}")
