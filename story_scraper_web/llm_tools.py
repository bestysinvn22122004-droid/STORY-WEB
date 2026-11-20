"""
Small Gemini helpers for the scraper tabs
=========================================
    paraphrase_title(title)      -> rewritten story title (same language)
    generate_cover_image(title)  -> (image_bytes, mime_type), 3:4 portrait

Configuration (environment variables, on top of the GEMINI_API_KEY(S) used
by video_analyzer):
    GEMINI_TEXT_MODEL      optional - model for the title rewrite (default gemini-2.5-flash)
    GEMINI_IMAGE_MODEL     optional - image model (default gemini-3.1-flash-image)
    GEMINI_IMAGE_API_KEYS  optional - comma-separated keys used ONLY for images
                           (image models have no free quota, so a billed key
                           usually has to go here); falls back to the normal keys
    COVER_IMAGE_ASPECT     optional - default "3:4"
"""
import os
import re
from typing import Optional, Tuple

from video_analyzer import VideoAnalyzerError, _api_keys, _get_client, _is_quota_error

TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
IMAGE_ASPECT = os.environ.get("COVER_IMAGE_ASPECT", "3:4")


class LLMToolError(Exception):
    """User-facing error (safe to show in the UI)."""


def is_configured() -> bool:
    return bool(_api_keys())


def _image_keys() -> list:
    own = [k.strip() for k in os.environ.get("GEMINI_IMAGE_API_KEYS", "").split(",") if k.strip()]
    return own or _api_keys()


def _with_key_rotation(keys: list, call):
    """Runs call(client) with each key until one is not out of quota."""
    if not keys:
        raise LLMToolError("Thiếu GEMINI_API_KEY trên server.")
    last = None
    for key in keys:
        try:
            return call(_get_client(key))
        except VideoAnalyzerError as exc:
            raise LLMToolError(str(exc))
        except Exception as exc:
            last = exc
            if _is_quota_error(exc):
                continue
            raise LLMToolError(f"Gemini lỗi: {str(exc)[:200]}")
    raise LLMToolError(f"Tất cả {len(keys)} key đều hết quota cho model này. ({str(last)[:120]})")


PARAPHRASE_PROMPT = """Rewrite the story title below so it says the same thing in different words.

Rules:
- Keep the same language as the original title.
- Keep every key fact, name, number and the emotional hook; do not invent new facts.
- Similar length to the original (never longer than 1.2x).
- Use natural title case, not ALL CAPS, even if the original is in capitals.
- Output ONLY the rewritten title on a single line: no quotes, no explanation, no numbering.

Original title:
{title}"""


def paraphrase_title(title: str, model: Optional[str] = None) -> str:
    title = " ".join((title or "").split())
    if not title:
        raise LLMToolError("Tiêu đề trống.")
    from google.genai import types

    def call(client):
        resp = client.models.generate_content(
            model=model or TEXT_MODEL,
            contents=PARAPHRASE_PROMPT.format(title=title),
            config=types.GenerateContentConfig(temperature=0.8),
        )
        return resp.text or ""

    out = _with_key_rotation(_api_keys(), call)
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    if not lines:
        raise LLMToolError("Model không trả về tiêu đề.")
    new = re.sub(r"^[\"“”'*#\s]+|[\"“”'*\s]+$", "", lines[0])
    if not new:
        raise LLMToolError("Model không trả về tiêu đề.")
    return new[:300]


IMAGE_PROMPT = """Create a dramatic, cinematic, photorealistic cover illustration for a story titled:

"{title}"

Show the key moment the title describes, with expressive characters and emotional lighting.
Portrait orientation, aspect ratio {aspect}. Do not render any text, letters, captions, logos or watermarks in the image."""


def generate_cover_image(title: str, model: Optional[str] = None) -> Tuple[bytes, str]:
    """Returns (bytes, mime_type) of a portrait cover image for the title."""
    title = " ".join((title or "").split())
    if not title:
        raise LLMToolError("Tiêu đề trống.")
    from google.genai import types
    model = model or IMAGE_MODEL
    prompt = IMAGE_PROMPT.format(title=title, aspect=IMAGE_ASPECT)

    def call(client):
        if model.startswith("imagen"):
            resp = client.models.generate_images(
                model=model, prompt=prompt,
                config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio=IMAGE_ASPECT),
            )
            img = resp.generated_images[0].image
            return img.image_bytes, (img.mime_type or "image/png")
        resp = client.models.generate_content(
            model=model, contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=IMAGE_ASPECT),
            ),
        )
        for cand in resp.candidates or []:
            for part in (cand.content.parts if cand.content else []) or []:
                data = getattr(part, "inline_data", None)
                if data and data.data:
                    return data.data, (data.mime_type or "image/png")
        raise LLMToolError("Model không trả về ảnh (có thể bị chặn bởi safety filter).")

    return _with_key_rotation(_image_keys(), call)


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "SIX INCHES FROM DEATH"
    print("paraphrase:", paraphrase_title(t))
    if "--image" in sys.argv:
        data, mime = generate_cover_image(t)
        open("cover_test.png", "wb").write(data)
        print("image:", len(data), mime)
