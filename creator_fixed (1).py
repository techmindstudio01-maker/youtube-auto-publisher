# creator.py
# TECHMIND STUDIO — AI YouTube Auto Publisher
# Production version — long video + Short + thumbnail + YouTube upload

import os
import re
import json
import time
import math
import random
import shutil
import subprocess
from pathlib import Path

import requests


# ============================================================
# CONFIG
# ============================================================

CHANNEL_NAME = "TECHMIND STUDIO"

BASE = Path("production")
LONG_DIR = BASE / "long"
SHORT_DIR = BASE / "short"
AUDIO_DIR = BASE / "audio"
THUMB_DIR = BASE / "thumbnail"

for d in [BASE, LONG_DIR, SHORT_DIR, AUDIO_DIR, THUMB_DIR]:
    d.mkdir(parents=True, exist_ok=True)

FPS = 30
LONG_W = 1920
LONG_H = 1080
SHORT_W = 1080
SHORT_H = 1920

VOICE = "en-US-ChristopherNeural"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing")


# ============================================================
# HELPERS
# ============================================================

def run(cmd, check=True):
    print("\nRUN:", " ".join(map(str, cmd)))

    result = subprocess.run(
        [str(x) for x in cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    print(result.stdout)

    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}"
        )

    return result


def clean_text(text):
    if not text:
        return ""

    text = str(text)
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = text.replace("\r", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def safe_filename(text):
    text = clean_text(text)
    text = re.sub(r"[^a-zA-Z0-9_-]+", "_", text)
    return text[:100].strip("_")


def get_duration(audio_path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path)
        ],
        capture_output=True,
        text=True,
        check=True
    )

    return float(result.stdout.strip())


# ============================================================
# GEMINI
# ============================================================

def gemini(prompt, retries=6):

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-3.5-flash-lite:generateContent"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.9,
            "maxOutputTokens": 7000
        }
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY
    }

    for attempt in range(1, retries + 1):

        print(f"\nGemini attempt {attempt}/{retries}")

        try:

            r = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=120
            )

            print("Gemini HTTP:", r.status_code)

            if r.status_code == 200:

                data = r.json()

                candidates = data.get("candidates", [])

                if not candidates:
                    raise RuntimeError("Gemini returned no candidates")

                parts = candidates[0].get("content", {}).get("parts", [])

                text = ""

                for part in parts:
                    if "text" in part:
                        text += part["text"]

                text = clean_text(text)

                if text:
                    return text

                raise RuntimeError("Gemini returned empty text")

            if r.status_code in [429, 500, 502, 503, 504]:

                wait = min(30, 3 * attempt)

                print(
                    f"Gemini temporary error {r.status_code}. "
                    f"Waiting {wait}s..."
                )

                time.sleep(wait)
                continue

            print(r.text)

            raise RuntimeError(
                f"Gemini API failed: HTTP {r.status_code}"
            )

        except requests.RequestException as e:

            print("Gemini network error:", e)

            if attempt == retries:
                raise

            time.sleep(3 * attempt)

    raise RuntimeError("Gemini failed after all retries")


# ============================================================
# CONTENT GENERATION
# ============================================================

def generate_content():

    prompt = f"""
You are the senior content producer for a YouTube channel named
{CHANNEL_NAME}.

Create ONE completely fresh, interesting and current AI/technology
video topic suitable for YouTube.

The final long video should be approximately 4 to 5 minutes.

The video must feel like a professional technology channel.

IMPORTANT:

- Strong opening hook.
- Original wording.
- Useful information.
- Easy natural English.
- No fake claims.
- No repetitive filler.
- No generic motivational content.
- Make the topic visually interesting.
- Explain practical examples.
- Finish with a strong conclusion.

Create exactly this JSON structure:

{{
  "title": "YouTube title with 1 or 2 relevant emojis",
  "description": "Professional YouTube description",
  "hashtags": ["#AI", "#Technology", "#..."],
  "tags": ["AI", "artificial intelligence", "technology", "..."],
  "topic": "topic name",
  "script": "complete narration script"
}}

The script must be around 650-800 words.

Return ONLY valid JSON.
"""

    raw = gemini(prompt)

    # remove accidental markdown fences
    raw = raw.strip()

    raw = re.sub(
        r"^```json\s*",
        "",
        raw,
        flags=re.I
    )

    raw = re.sub(
        r"\s*```$",
        "",
        raw
    )

    try:
        data = json.loads(raw)
    except Exception:

        # attempt to recover JSON block
        start = raw.find("{")
        end = raw.rfind("}")

        if start == -1 or end == -1:
            raise RuntimeError(
                "Gemini did not return valid JSON"
            )

        data = json.loads(raw[start:end + 1])

    required = [
        "title",
        "description",
        "hashtags",
        "tags",
        "topic",
        "script"
    ]

    for key in required:
        if key not in data:
            raise RuntimeError(
                f"Missing content field: {key}"
            )

    return data


# ============================================================
# EDGE TTS
# ============================================================

def generate_voice(text, output_path):

    text = clean_text(text)

    temp_txt = AUDIO_DIR / "voice_input.txt"

    temp_txt.write_text(
        text,
        encoding="utf-8"
    )

    run([
        "edge-tts",
        "--voice",
        VOICE,
        "--rate=-5%",
        "--text",
        text,
        "--write-media",
        str(output_path)
    ])

    if not output_path.exists():
        raise RuntimeError(
            f"Voice generation failed: {output_path}"
        )


# ============================================================
# IMAGE SEARCH
# ============================================================

def search_wikimedia(query):

    url = "https://commons.wikimedia.org/w/api.php"

    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": 10,
        "prop": "imageinfo",
        "iiprop": "url|size",
        "iiurlwidth": 2200
    }

    r = requests.get(
        url,
        params=params,
        timeout=30
    )

    r.raise_for_status()

    data = r.json()

    pages = data.get("query", {}).get("pages", {})

    results = []

    for page in pages.values():

        info = page.get("imageinfo", [])

        if not info:
            continue

        item = info[0]

        image_url = (
            item.get("thumburl")
            or item.get("url")
        )

        if not image_url:
            continue

        width = item.get("thumbwidth", 0)
        height = item.get("thumbheight", 0)

        if width < 1000 or height < 600:
            continue

        results.append(image_url)

    return results


def download_image(query, output_path):

    print(
        f"\nSEARCH REAL VISUAL: {query}"
    )

    urls = search_wikimedia(query)

    if not urls:
        raise RuntimeError(
            f"No suitable Wikimedia image found for: {query}"
        )

    random.shuffle(urls)

    for url in urls:

        try:

            print("IMAGE:", url)

            r = requests.get(
                url,
                timeout=60,
                headers={
                    "User-Agent":
                    "TechMindStudioYouTubeBot/1.0"
                }
            )

            r.raise_for_status()

            content = r.content

            if len(content) < 100_000:
                continue

            output_path.write_bytes(content)

            print(
                "Downloaded:",
                output_path,
                len(content),
                "bytes"
            )

            return

        except Exception as e:

            print(
                "Image failed:",
                e
            )

    raise RuntimeError(
        f"Could not download image for: {query}"
    )


# ============================================================
# BRAND OVERLAY
# ONLY CHANNEL NAME
# ============================================================

def add_brand_overlay(
    input_video,
    output_video,
    vertical=False
):

    W = SHORT_W if vertical else LONG_W
    H = SHORT_H if vertical else LONG_H

    # Small professional bottom-left branding.
    # No title.
    # No captions.
    # No cards.
    # No other text.

    fontsize = 34 if not vertical else 38

    filter_text = (
        f"drawtext="
        f"fontcolor=white@0.82:"
        f"fontsize={fontsize}:"
        f"font=DejaVuSans-Bold:"
        f"text='{CHANNEL_NAME}':"
        f"x=45:"
        f"y=h-th-38:"
        f"shadowcolor=black@0.65:"
        f"shadowx=2:"
        f"shadowy=2"
    )

    run([
        "ffmpeg",
        "-y",
        "-i",
        str(input_video),
        "-vf",
        filter_text,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(output_video)
    ])


# ============================================================
# ANIMATED SCENE
# FIXED ZOOMPAN FILTER
# ============================================================

def animated_scene(
    image_path,
    audio_path,
    output_path,
    motion="push_in",
    vertical=False
):

    W, H = (
        (SHORT_W, SHORT_H)
        if vertical
        else
        (LONG_W, LONG_H)
    )

    duration = get_duration(audio_path)

    # Oversize source before crop.
    # This gives room for camera movement.

    SW = int(W * 1.14)
    SH = int(H * 1.14)

    base = (
        f"scale={SW}:{SH}:"
        f"force_original_aspect_ratio=increase,"
        f"crop={SW}:{SH},"
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Every zoompan expression is separately quoted.
    # This fixes the previous Scene 6 error:
    #
    # "...*on/292:y='..."
    #
    # --------------------------------------------------------

    if motion == "push_in":

        zoom = "1.02+0.00008*on"

        x = (
            "iw/2-(iw/zoom/2)"
        )

        y = (
            "ih/2-(ih/zoom/2)"
        )

    elif motion == "pull_out":

        zoom = "1.095-0.00008*on"

        x = (
            "iw/2-(iw/zoom/2)"
        )

        y = (
            "ih/2-(ih/zoom/2)"
        )

    elif motion == "track_left":

        zoom = "1.055"

        x = (
            "(iw-iw/zoom)*"
            "(0.5+0.42*sin(on/180))"
        )

        y = (
            "ih/2-(ih/zoom/2)"
        )

    elif motion == "track_right":

        zoom = "1.055"

        x = (
            "(iw-iw/zoom)*"
            "(0.5-0.42*sin(on/180))"
        )

        y = (
            "ih/2-(ih/zoom/2)"
        )

    elif motion == "rise":

        zoom = "1.05"

        x = (
            "iw/2-(iw/zoom/2)"
        )

        y = (
            "(ih-ih/zoom)*"
            "(0.5-0.42*sin(on/180))"
        )

    elif motion == "descend":

        zoom = "1.05"

        x = (
            "iw/2-(iw/zoom/2)"
        )

        y = (
            "(ih-ih/zoom)*"
            "(0.5+0.42*sin(on/180))"
        )

    elif motion == "orbit":

        zoom = "1.05"

        x = (
            "(iw-iw/zoom)*"
            "(0.5+0.22*sin(on/210))"
        )

        y = (
            "(ih-ih/zoom)*"
            "(0.5+0.16*cos(on/210))"
        )

    else:

        zoom = "1.035+0.00004*on"

        x = (
            "iw/2-(iw/zoom/2)"
        )

        y = (
            "ih/2-(ih/zoom/2)"
        )

    # --------------------------------------------------------
    # SAFE FILTER CONSTRUCTION
    # --------------------------------------------------------

    vf = (
        base
        + "zoompan="
        + f"z='{zoom}':"
        + f"x='{x}':"
        + f"y='{y}':"
        + "d=1:"
        + f"s={W}x{H}:"
        + "fps=30,"
        + "setsar=1,"
        + "format=yuv420p"
    )

    run([
        "ffmpeg",
        "-y",

        "-loop",
        "1",

        "-i",
        str(image_path),

        "-i",
        str(audio_path),

        "-vf",
        vf,

        "-t",
        f"{duration:.3f}",

        "-r",
        "30",

        "-c:v",
        "libx264",

        "-preset",
        "medium",

        "-crf",
        "18",

        "-pix_fmt",
        "yuv420p",

        "-c:a",
        "aac",

        "-b:a",
        "192k",

        "-ar",
        "48000",

        "-shortest",

        "-movflags",
        "+faststart",

        str(output_path)
    ])


# ============================================================
# LONG VIDEO
# ============================================================

def make_long_video(content):

    script = content["script"]

    # Split script into approximately 10 scenes.
    sentences = re.split(
        r"(?<=[.!?])\s+",
        script
    )

    sentences = [
        x.strip()
        for x in sentences
        if x.strip()
    ]

    scene_count = 10

    chunks = []

    if len(sentences) < scene_count:

        # fallback: split by words
        words = script.split()

        chunk_size = max(
            1,
            math.ceil(
                len(words) / scene_count
            )
        )

        for i in range(
            0,
            len(words),
            chunk_size
        ):

            chunks.append(
                " ".join(
                    words[
                        i:i + chunk_size
                    ]
                )
            )

    else:

        chunk_size = math.ceil(
            len(sentences) / scene_count
        )

        for i in range(
            0,
            len(sentences),
            chunk_size
        ):

            chunks.append(
                " ".join(
                    sentences[
                        i:i + chunk_size
                    ]
                )
            )

    # Guarantee max 10 scenes
    chunks = chunks[:scene_count]

    motions = [
        "push_in",
        "track_left",
        "pull_out",
        "rise",
        "track_right",
        "orbit",
        "push_in",
        "descend",
        "track_left",
        "pull_out"
    ]

    scene_files = []

    # --------------------------------------------------------
    # VISUAL SEARCH PROMPTS
    # --------------------------------------------------------

    topic = content["topic"]

    for i, chunk in enumerate(chunks):

        scene_no = i + 1

        print(
            f"\nLONG SCENE {scene_no}/{len(chunks)}"
        )

        # Ask Gemini for a specific photographic search phrase.
        visual_prompt = f"""
For this YouTube video topic:

{topic}

Scene narration:

{chunk}

Give ONE concise Wikimedia Commons image-search query.

The query must describe a real photographic visual that directly
matches this scene.

Prefer:
- real people
- real smartphones
- real computers
- real AI labs
- real technology
- real offices
- real robots
- real data centers
- real hardware
- real-world technology situations

Avoid:
- logos
- text screenshots
- posters
- illustrations
- cartoons
- abstract backgrounds
- generic landscapes

Return ONLY the search query.
"""

        try:
            query = gemini(
                visual_prompt,
                retries=4
            )

            query = clean_text(query)

        except Exception:

            query = (
                "artificial intelligence technology "
                "computer"
            )

        image_path = LONG_DIR / (
            f"scene_{scene_no:02d}.jpg"
        )

        audio_path = AUDIO_DIR / (
            f"long_{scene_no:02d}.mp3"
        )

        scene_video = LONG_DIR / (
            f"scene_{scene_no:02d}.mp4"
        )

        generate_voice(
            chunk,
            audio_path
        )

        download_image(
            query,
            image_path
        )

        animated_scene(
            image_path,
            audio_path,
            scene_video,
            motion=motions[i % len(motions)],
            vertical=False
        )

        scene_files.append(
            scene_video
        )

    # --------------------------------------------------------
    # CONCAT
    # --------------------------------------------------------

    concat_file = LONG_DIR / "concat.txt"

    with concat_file.open(
        "w",
        encoding="utf-8"
    ) as f:

        for video in scene_files:

            f.write(
                f"file '{video.resolve()}'\n"
            )

    raw_long = LONG_DIR / "long_raw.mp4"

    run([
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(raw_long)
    ])

    # --------------------------------------------------------
    # BRAND
    # --------------------------------------------------------

    final_long = LONG_DIR / "final_long.mp4"

    add_brand_overlay(
        raw_long,
        final_long,
        vertical=False
    )

    return final_long


# ============================================================
# SHORT
# ============================================================

def make_short(content):

    script = content["script"]

    # Use first strong part of narration.
    sentences = re.split(
        r"(?<=[.!?])\s+",
        script
    )

    short_sentences = sentences[:5]

    short_script = " ".join(
        short_sentences
    )

    # Keep Short reasonably concise.
    words = short_script.split()

    if len(words) > 120:

        short_script = " ".join(
            words[:120]
        )

    audio_path = AUDIO_DIR / "short.mp3"

    generate_voice(
        short_script,
        audio_path
    )

    topic = content["topic"]

    visual_prompt = f"""
Create one Wikimedia Commons image-search query for a YouTube Short
about:

{topic}

The image should be a real HD photograph directly related to the topic.

Prefer a strong visual subject:
AI, technology, smartphone, computer, robot, data center,
developer, futuristic hardware or real technology use.

Avoid illustrations, logos, text graphics and cartoons.

Return ONLY the query.
"""

    try:
        query = gemini(
            visual_prompt,
            retries=4
        )
        query = clean_text(query)

    except Exception:

        query = (
            "artificial intelligence technology "
            "smartphone computer"
        )

    image_path = SHORT_DIR / "short.jpg"

    download_image(
        query,
        image_path
    )

    raw_short = SHORT_DIR / "short_raw.mp4"

    animated_scene(
        image_path,
        audio_path,
        raw_short,
        motion="push_in",
        vertical=True
    )

    final_short = SHORT_DIR / "final_short.mp4"

    add_brand_overlay(
        raw_short,
        final_short,
        vertical=True
    )

    return final_short


# ============================================================
# THUMBNAIL
# ============================================================

def make_thumbnail(content):

    title = content["title"]

    # Find one strong topic image.
    query = (
        content["topic"]
        + " technology artificial intelligence"
    )

    image_path = THUMB_DIR / "thumbnail_source.jpg"

    try:

        download_image(
            query,
            image_path
        )

    except Exception:

        print(
            "Thumbnail source failed. "
            "Using first long scene image."
        )

        first_scene = LONG_DIR / "scene_01.jpg"

        if first_scene.exists():
            shutil.copy(
                first_scene,
                image_path
            )
        else:
            return None

    output = THUMB_DIR / "thumbnail.jpg"

    # Professional YouTube thumbnail.
    # Thumbnail can contain title text.

    safe_title = (
        title
        .replace("'", "")
        .replace(":", "")
        .replace('"', "")
    )

    drawtext = (
        "drawtext="
        "font=DejaVuSans-Bold:"
        "fontcolor=white:"
        "fontsize=72:"
        "borderw=5:"
        "bordercolor=black@0.75:"
        f"text='{safe_title}':"
        "x=80:"
        "y=h-th-90:"
        "max_glyphs=45"
    )

    run([
        "ffmpeg",
        "-y",
        "-i",
        str(image_path),
        "-vf",
        (
            "scale=1280:720:"
            "force_original_aspect_ratio=increase,"
            "crop=1280:720,"
            + drawtext
        ),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output)
    ])

    return output


# ============================================================
# METADATA
# ============================================================

def save_metadata(content):

    metadata = {
        "title": clean_text(
            content["title"]
        ),
        "description": clean_text(
            content["description"]
        ),
        "hashtags": content["hashtags"],
        "tags": content["tags"],
        "topic": clean_text(
            content["topic"]
        )
    }

    # Ensure hashtags
    fixed_hashtags = []

    for tag in metadata["hashtags"]:

        tag = str(tag).strip()

        if not tag:
            continue

        if not tag.startswith("#"):
            tag = "#" + tag

        fixed_hashtags.append(tag)

    metadata["hashtags"] = fixed_hashtags

    # Add hashtags to description.
    hashtag_text = " ".join(
        fixed_hashtags
    )

    if hashtag_text:

        if hashtag_text not in metadata["description"]:

            metadata["description"] += (
                "\n\n"
                + hashtag_text
            )

    metadata_path = BASE / "metadata.json"

    metadata_path.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(
        "\nMETADATA SAVED:",
        metadata_path
    )

    print(
        "\nTITLE:",
        metadata["title"]
    )

    print(
        "\nHASHTAGS:",
        " ".join(metadata["hashtags"])
    )

    return metadata



# ============================================================
# YOUTUBE UPLOAD
# ============================================================

YOUTUBE_TOKEN_JSON = os.environ.get("YOUTUBE_TOKEN_JSON", "").strip()
YOUTUBE_PRIVACY = os.environ.get("YOUTUBE_PRIVACY", "public").strip().lower()


def get_youtube_service():
    if not YOUTUBE_TOKEN_JSON:
        raise RuntimeError("YOUTUBE_TOKEN_JSON is missing")

    data = json.loads(YOUTUBE_TOKEN_JSON)

    if "installed" in data or "web" in data:
        raise RuntimeError(
            "YOUTUBE_TOKEN_JSON must be the working authorized-user token JSON, "
            "not the OAuth client secret."
        )

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get(
            "token_uri",
            "https://oauth2.googleapis.com/token"
        ),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes") or [
            "https://www.googleapis.com/auth/youtube.upload"
        ],
    )

    if creds.expired and creds.refresh_token:
        print("Refreshing YouTube token...")
        creds.refresh(Request())

    if not creds.valid:
        raise RuntimeError("YouTube credentials are invalid or expired.")

    return build(
        "youtube",
        "v3",
        credentials=creds,
        cache_discovery=False,
    )


def youtube_tags(tags):
    result = []
    seen = set()

    for tag in tags:
        tag = clean_text(tag).replace("#", "").strip()
        if not tag:
            continue
        if tag.lower() in seen:
            continue
        seen.add(tag.lower())
        result.append(tag)

    while len(",".join(result)) > 480:
        result.pop()

    return result


def upload_video(video_path, content, thumbnail=None, short=False):
    from googleapiclient.http import MediaFileUpload

    service = get_youtube_service()

    title = clean_text(content["title"])
    if short and "#Shorts" not in title:
        title += " #Shorts"

    description = clean_text(content["description"])

    hashtags = []
    for item in content.get("hashtags", []):
        item = str(item).strip()
        if item and not item.startswith("#"):
            item = "#" + item
        if item:
            hashtags.append(item)

    hashtag_text = " ".join(hashtags)
    if hashtag_text and hashtag_text not in description:
        description += "\n\n" + hashtag_text

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": youtube_tags(content.get("tags", [])),
            "categoryId": "28",
        },
        "status": {
            "privacyStatus": YOUTUBE_PRIVACY,
            "selfDeclaredMadeForKids": False,
        },
    }

    print("\nUPLOAD:", title)

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=8 * 1024 * 1024,
    )

    request = service.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None

    while response is None:
        status, response = request.next_chunk()
        if status:
            print("Upload:", int(status.progress() * 100), "%")

    video_id = response["id"]

    if thumbnail and Path(thumbnail).exists() and not short:
        print("Uploading thumbnail...")
        service.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(
                str(thumbnail),
                mimetype="image/jpeg",
            ),
        ).execute()

    print("Uploaded:", video_id)

    return video_id


def upload_all(long_video, short_video, thumbnail, content):
    long_id = upload_video(
        long_video,
        content,
        thumbnail=thumbnail,
        short=False,
    )

    short_id = upload_video(
        short_video,
        content,
        thumbnail=None,
        short=True,
    )

    result = {
        "long_video_id": long_id,
        "long_video_url": f"https://www.youtube.com/watch?v={long_id}",
        "short_video_id": short_id,
        "short_video_url": f"https://www.youtube.com/watch?v={short_id}",
    }

    (BASE / "youtube_upload.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "\n=============================================="
    )

    print(
        " TECHMIND STUDIO AI VIDEO PIPELINE"
    )

    print(
        "==============================================\n"
    )

    # --------------------------------------------------------
    # 1. Generate fresh topic/content
    # --------------------------------------------------------

    content = generate_content()

    print(
        "\nTOPIC:",
        content["topic"]
    )

    print(
        "\nTITLE:",
        content["title"]
    )

    # --------------------------------------------------------
    # 2. Save metadata
    # --------------------------------------------------------

    metadata = save_metadata(
        content
    )

    # --------------------------------------------------------
    # 3. Long video
    # --------------------------------------------------------

    print(
        "\n=============================================="
    )

    print(
        "CREATING LONG VIDEO"
    )

    print(
        "=============================================="
    )

    long_video = make_long_video(
        content
    )

    print(
        "\nLONG VIDEO READY:",
        long_video
    )

    # --------------------------------------------------------
    # 4. Short
    # --------------------------------------------------------

    print(
        "\n=============================================="
    )

    print(
        "CREATING SHORT"
    )

    print(
        "=============================================="
    )

    short_video = make_short(
        content
    )

    print(
        "\nSHORT READY:",
        short_video
    )

    # --------------------------------------------------------
    # 5. Thumbnail
    # --------------------------------------------------------

    print(
        "\n=============================================="
    )

    print(
        "CREATING THUMBNAIL"
    )

    print(
        "=============================================="
    )

    thumbnail = make_thumbnail(
        content
    )

    print(
        "\nTHUMBNAIL READY:",
        thumbnail
    )

    # --------------------------------------------------------
    # 6. Final output manifest
    # --------------------------------------------------------

    manifest = {
        "title": metadata["title"],
        "topic": metadata["topic"],
        "description": metadata["description"],
        "hashtags": metadata["hashtags"],
        "tags": metadata["tags"],
        "long_video": str(long_video),
        "short_video": str(short_video),
        "thumbnail": (
            str(thumbnail)
            if thumbnail
            else None
        )
    }

    manifest_path = BASE / "manifest.json"

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(
        "\n=============================================="
    )

    print(
        "ALL CONTENT CREATED SUCCESSFULLY"
    )

    print(
        "==============================================\n"
    )

    print(
        "LONG:",
        long_video
    )

    print(
        "SHORT:",
        short_video
    )

    print(
        "THUMBNAIL:",
        thumbnail
    )

    print(
        "METADATA:",
        BASE / "metadata.json"
    )

    # --------------------------------------------------------
    # 6. YouTube upload
    # --------------------------------------------------------

    youtube_result = upload_all(
        long_video,
        short_video,
        thumbnail,
        content,
    )

    manifest = {
        "title": metadata["title"],
        "topic": metadata["topic"],
        "description": metadata["description"],
        "hashtags": metadata["hashtags"],
        "tags": metadata["tags"],
        "long_video": str(long_video),
        "short_video": str(short_video),
        "thumbnail": str(thumbnail) if thumbnail else None,
        "youtube": youtube_result,
    }

    (BASE / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nALL CONTENT CREATED AND UPLOADED SUCCESSFULLY")
    print(youtube_result)


if __name__ == "__main__":
    main()