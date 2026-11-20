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
    CF_ACCOUNT_ID          } when both are set, covers are generated with
    CF_AI_TOKEN            } Cloudflare Workers AI (free daily quota) instead of Gemini
    CF_IMAGE_MODEL         optional - default @cf/black-forest-labs/flux-1-schnell
    CF_IMAGE_STEPS         optional - default 6 (max 8 for flux schnell)
"""
import io
import os
import re
import base64

import requests
from typing import Optional, Tuple

from video_analyzer import VideoAnalyzerError, _api_keys, _get_client, _is_quota_error

TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
IMAGE_ASPECT = os.environ.get("COVER_IMAGE_ASPECT", "3:4")
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "").strip()
CF_AI_TOKEN = os.environ.get("CF_AI_TOKEN", "").strip()
CF_IMAGE_MODEL = os.environ.get("CF_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell")
CF_IMAGE_STEPS = int(os.environ.get("CF_IMAGE_STEPS", "6"))


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



# ---------------------------------------------------------------------------
# Cloudflare Workers AI cover (title -> scene prompt -> FLUX -> crop to 3:4)
# ---------------------------------------------------------------------------
SCENE_PROMPT = """Turn this story title into ONE image-generation prompt (max 70 words) describing a single dramatic, photorealistic scene that illustrates the story.

Rules:
- Describe only what is visible: who (age, clothing, expression), where, what is happening, lighting, camera framing.
- Vertical portrait composition with the main subject centered.
- Family-friendly wording: no words like death, kill, blood, weapon, naked. Imply danger through expressions and atmosphere.
- Do NOT quote the title and do NOT ask for any text, sign, caption or logo.
{extra}- Output only the prompt, one paragraph.

Story title: {title}"""

SAFER_RULE = ("- A safety filter rejected the previous attempt. Do not mention babies, infants, children, bodies, "
              "pregnancy, injuries or peril; show only adults and/or animals in a calm but tense moment.\n")


def title_to_scene(title: str, safer: bool = False) -> str:
    from google.genai import types

    def call(client):
        resp = client.models.generate_content(
            model=TEXT_MODEL,
            contents=SCENE_PROMPT.format(title=title, extra=SAFER_RULE if safer else ""),
            config=types.GenerateContentConfig(temperature=0.7),
        )
        return resp.text or ""

    scene = " ".join(_with_key_rotation(_api_keys(), call).split())
    if not scene:
        raise LLMToolError("Model không trả về mô tả cảnh cho ảnh bìa.")
    return scene


def _crop_to_aspect(raw: bytes) -> Tuple[bytes, str]:
    """Center-crops to COVER_IMAGE_ASPECT and re-encodes as JPEG."""
    from PIL import Image
    try:
        aw, ah = (int(x) for x in IMAGE_ASPECT.split(":"))
    except ValueError:
        aw, ah = 3, 4
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.size
    if w * ah > h * aw:      # too wide -> trim the sides
        nw = h * aw // ah
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    elif w * ah < h * aw:    # too tall -> trim top/bottom
        nh = w * ah // aw
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=90)
    return buf.getvalue(), "image/jpeg"


def _cloudflare_image(prompt: str) -> bytes:
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{CF_IMAGE_MODEL}"
    try:
        resp = requests.post(url, headers={"Authorization": f"Bearer {CF_AI_TOKEN}"},
                             json={"prompt": prompt, "steps": CF_IMAGE_STEPS}, timeout=120)
    except requests.RequestException as exc:
        raise LLMToolError(f"Không kết nối được Cloudflare AI: {exc}")
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.ok and body.get("success") and (body.get("result") or {}).get("image"):
        return base64.b64decode(body["result"]["image"])
    msg = "; ".join(str(e.get("message", "")) for e in body.get("errors") or []) or resp.text[:200]
    if "nsfw" in msg.lower():
        raise _NSFWRejected(msg)
    if resp.status_code == 429 or "neurons" in msg.lower() or "quota" in msg.lower():
        raise LLMToolError("Cloudflare AI đã hết hạn mức miễn phí hôm nay.")
    raise LLMToolError(f"Cloudflare AI lỗi (HTTP {resp.status_code}): {msg[:200]}")


class _NSFWRejected(Exception):
    pass


def _cover_via_cloudflare(title: str) -> Tuple[bytes, str]:
    suffix = (" Cinematic lighting, shallow depth of field, ultra detailed, photorealistic. "
              "The image contains no text or writing.")
    last = ""
    for attempt in range(3):
        scene = title_to_scene(title, safer=attempt > 0)
        try:
            return _crop_to_aspect(_cloudflare_image(scene + suffix))
        except _NSFWRejected as exc:
            last = str(exc)
    raise LLMToolError(f"Bộ lọc nội dung của Cloudflare từ chối cả 3 lần thử. ({last[:120]})")


def generate_cover_image(title: str, model: Optional[str] = None) -> Tuple[bytes, str]:
    """Returns (bytes, mime_type) of a portrait cover image for the title."""
    title = " ".join((title or "").split())
    if not title:
        raise LLMToolError("Tiêu đề trống.")
    if CF_ACCOUNT_ID and CF_AI_TOKEN and not model:
        return _cover_via_cloudflare(title)
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
