# creator.py
# TECHMIND STUDIO — Automatic AI YouTube Publisher (Optimized & Fixed)

import os
import re
import json
import time
import random
import subprocess
from pathlib import Path
import requests

# ============================================================
# CONFIG
# ============================================================

CHANNEL = "TechMind Studio"

BASE = Path("production")
LONG = BASE / "long"
SHORT = BASE / "short"
AUDIO = BASE / "audio"
THUMB = BASE / "thumbnail"

for d in [LONG, SHORT, AUDIO, THUMB]:
    d.mkdir(parents=True, exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
YOUTUBE_TOKEN_JSON = os.getenv("YOUTUBE_TOKEN_JSON", "").strip()

VOICE = "en-US-ChristopherNeural"

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing")

if not YOUTUBE_TOKEN_JSON:
    raise RuntimeError("YOUTUBE_TOKEN_JSON is missing")


# ============================================================
# HELPERS
# ============================================================

def run(cmd):
    print("\nRUN:", " ".join(map(str, cmd)))
    p = subprocess.run(
        [str(x) for x in cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    print(p.stdout)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {p.returncode}")
    return p


def clean(s):
    s = str(s or "")
    s = re.sub(r"```(?:json)?", "", s, flags=re.I)
    s = s.replace("```", "")
    return s.strip()


def duration(path):
    p = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path)
        ],
        capture_output=True,
        text=True,
        check=True
    )
    return float(p.stdout.strip())


# ============================================================
# GEMINI API
# ============================================================

def gemini(prompt, retries=6):
    models = [
        "gemini-2.5-flash",
        "gemini-2.0-flash"
    ]
    last_error = None

    for attempt in range(1, retries + 1):
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.85,
                    "maxOutputTokens": 8192
                }
            }

            try:
                r = requests.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": GEMINI_API_KEY
                    },
                    json=payload,
                    timeout=120
                )
                print(f"Gemini: {model} -> HTTP {r.status_code}")

                if r.status_code == 200:
                    data = r.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        continue

                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(part.get("text", "") for part in parts if "text" in part)
                    text = clean(text)

                    if text:
                        return text

                elif r.status_code in [429, 500, 502, 503, 504]:
                    last_error = r.text

                elif r.status_code == 404:
                    continue

                else:
                    raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:500]}")

            except requests.RequestException as e:
                last_error = str(e)

        wait = min(30, attempt * 4)
        print(f"Gemini retry in {wait}s...")
        time.sleep(wait)

    raise RuntimeError("Gemini failed after retries: " + str(last_error))


# ============================================================
# CONTENT GENERATION
# ============================================================

def create_content():
    prompt = f"""
You are the senior producer for {CHANNEL}.
Create ONE fresh AI/technology YouTube topic.
The long video must be 4 to 5 minutes and around 700-850 spoken words.
Create 8 visually different scenes for the long video.
Each scene needs:
- narration
- visual_query

Also create a 40-55 second Short using 4 scenes.

Requirements:
LONG VIDEO:
- powerful first 10 seconds
- natural conversational English
- useful information & practical examples
- no fake facts, no repetitive filler
- strong ending

SHORT:
- fast hook, useful, 4 scenes, vertical-video friendly

TITLE:
- under 90 characters, clickable but truthful, include 1 or 2 relevant AI/tech emojis

DESCRIPTION:
- professional, include hashtags

TAGS:
- 12 to 15 YouTube tags

Return ONLY valid JSON:
{{
  "topic": "...",
  "title": "...",
  "description": "...",
  "hashtags": ["#AI", "#Technology"],
  "tags": ["AI", "artificial intelligence"],
  "long_scenes": [
    {{
      "narration": "...",
      "visual_query": "..."
    }}
  ],
  "short_scenes": [
    {{
      "narration": "...",
      "visual_query": "..."
    }}
  ]
}}
"""
    raw = gemini(prompt)
    start = raw.find("{")
    end = raw.rfind("}")

    if start < 0 or end < 0:
        raise RuntimeError("Gemini returned invalid JSON")

    data = json.loads(raw[start:end + 1])

    if len(data.get("long_scenes", [])) < 6:
        raise RuntimeError("Not enough long-video scenes")

    if len(data.get("short_scenes", [])) < 4:
        raise RuntimeError("Not enough Short scenes")

    return data


# ============================================================
# EDGE TTS
# ============================================================

def voice(text, output):
    run([
        "edge-tts",
        "--voice", VOICE,
        "--rate=-5%",
        "--text", text,
        "--write-media", str(output)
    ])

    if not output.exists():
        raise RuntimeError("Voice file was not created")


# ============================================================
# WIKIMEDIA IMAGE SEARCH
# ============================================================

def find_images(query):
    r = requests.get(
        "https://commons.wikimedia.org/w/api.php",
        params={
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": 20,
            "prop": "imageinfo",
            "iiprop": "url|size",
            "iiurlwidth": 2200
        },
        timeout=40
    )
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    urls = []

    for page in pages.values():
        info = page.get("imageinfo", [])
        if not info:
            continue
        item = info[0]
        url = item.get("thumburl") or item.get("url")
        if url:
            urls.append(url)

    return urls


def download_image(query, output):
    print("\nIMAGE SEARCH:", query)
    urls = find_images(query)
    random.shuffle(urls)

    for url in urls:
        try:
            r = requests.get(
                url,
                timeout=60,
                headers={"User-Agent": "TechMindStudio/1.0"}
            )
            r.raise_for_status()
            if len(r.content) < 30000:
                continue
            output.write_bytes(r.content)
            print("IMAGE OK:", output)
            return
        except Exception as e:
            print("Image failed:", e)

    raise RuntimeError("No usable image found for query: " + query)


# ============================================================
# SCENE VIDEO (FFMPEG)
# ============================================================

def make_scene(image, audio, output, motion):
    d = duration(audio)

    if motion == "left":
        x = "(iw-iw/zoom)*(0.5+0.35*sin(on/180))"
        y = "ih/2-(ih/zoom/2)"
        z = "1.05"
    elif motion == "right":
        x = "(iw-iw/zoom)*(0.5-0.35*sin(on/180))"
        y = "ih/2-(ih/zoom/2)"
        z = "1.05"
    elif motion == "up":
        x = "iw/2-(iw/zoom/2)"
        y = "(ih-ih/zoom)*(0.5-0.35*sin(on/180))"
        z = "1.05"
    elif motion == "down":
        x = "iw/2-(iw/zoom/2)"
        y = "(ih-ih/zoom)*(0.5+0.35*sin(on/180))"
        z = "1.05"
    else:
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
        z = "1.02+0.00008*on"

    vf = (
        "scale=2200:1240:"
        "force_original_aspect_ratio=increase,"
        "crop=2200:1240,"
        "zoompan="
        f"z='{z}':"
        f"x='{x}':"
        f"y='{y}':"
        "d=1:"
        "s=1920x1080:"
        "fps=30,"
        "format=yuv420p"
    )

    run([
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", str(image),
        "-i", str(audio),
        "-vf", vf,
        "-t", str(d),
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "19",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output)
    ])


# ============================================================
# LONG VIDEO
# ============================================================

def create_long(data):
    scenes = data["long_scenes"]
    videos = []
    motions = ["zoom", "left", "right", "up", "down", "zoom", "left", "right"]

    for i, scene in enumerate(scenes):
        n = i + 1
        print(f"\n===== LONG SCENE {n}/{len(scenes)} =====")

        narration = scene["narration"]
        query = scene["visual_query"]

        audio = AUDIO / f"long_{n:02d}.mp3"
        image = LONG / f"scene_{n:02d}.jpg"
        video = LONG / f"scene_{n:02d}.mp4"

        voice(narration, audio)
        download_image(query, image)
        make_scene(image, audio, video, motions[i % len(motions)])
        videos.append(video)

    concat = LONG / "concat.txt"
    with concat.open("w", encoding="utf-8") as f:
        for video in videos:
            f.write(f"file '{video.resolve()}'\n")

    raw = LONG / "raw_long.mp4"
    run([
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat),
        "-c", "copy",
        "-movflags", "+faststart",
        str(raw)
    ])

    final = LONG / "final_long.mp4"
    run([
        "ffmpeg",
        "-y",
        "-i", str(raw),
        "-vf", (
            "drawtext="
            "fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            "fontcolor=white@0.80:"
            "fontsize=34:"
            "text='TechMind Studio':"
            "x=45:"
            "y=h-th-35:"
            "shadowcolor=black@0.7:"
            "shadowx=2:"
            "shadowy=2"
        ),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(final)
    ])

    return final


# ============================================================
# SHORT
# ============================================================

def create_short(data):
    scenes = data["short_scenes"]
    videos = []

    for i, scene in enumerate(scenes):
        n = i + 1
        audio = AUDIO / f"short_{n:02d}.mp3"
        image = SHORT / f"scene_{n:02d}.jpg"
        video = SHORT / f"scene_{n:02d}.mp4"

        voice(scene["narration"], audio)
        download_image(scene["visual_query"], image)
        d = duration(audio)

        vf = (
            "scale=1080:1920:"
            "force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "zoompan="
            "z='1.02+0.00008*on':"
            "x='iw/2-(iw/zoom/2)':"
            "y='ih/2-(ih/zoom/2)':"
            "d=1:"
            "s=1080x1920:"
            "fps=30,"
            "format=yuv420p"
        )

        run([
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-i", str(image),
            "-i", str(audio),
            "-vf", vf,
            "-t", str(d),
            "-r", "30",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "160k",
            "-shortest",
            "-movflags", "+faststart",
            str(video)
        ])
        videos.append(video)

    concat = SHORT / "concat.txt"
    with concat.open("w", encoding="utf-8") as f:
        for video in videos:
            f.write(f"file '{video.resolve()}'\n")

    raw = SHORT / "raw_short.mp4"
    run([
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat),
        "-c", "copy",
        "-movflags", "+faststart",
        str(raw)
    ])

    final = SHORT / "final_short.mp4"
    run([
        "ffmpeg",
        "-y",
        "-i", str(raw),
        "-vf", (
            "drawtext="
            "fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            "fontcolor=white@0.82:"
            "fontsize=38:"
            "text='TechMind Studio':"
            "x=35:"
            "y=h-th-45:"
            "shadowcolor=black@0.7:"
            "shadowx=2:"
            "shadowy=2"
        ),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "19",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(final)
    ])

    return final


# ============================================================
# THUMBNAIL
# ============================================================

def create_thumbnail(data):
    image = THUMB / "source.jpg"
    download_image(data["topic"] + " artificial intelligence technology", image)

    title = data["title"].replace("'", "").replace('"', "").replace(":", "")
    output = THUMB / "thumbnail.jpg"

    run([
        "ffmpeg",
        "-y",
        "-i", str(image),
        "-vf", (
            "scale=1280:720:"
            "force_original_aspect_ratio=increase,"
            "crop=1280:720,"
            "drawtext="
            "fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            "fontcolor=white:"
            "fontsize=62:"
            "borderw=5:"
            "bordercolor=black:"
            f"text='{title[:45]}':"
            "x=60:"
            "y=h-th-65"
        ),
        "-frames:v", "1",
        "-q:v", "2",
        str(output)
    ])
    return output


# ============================================================
# METADATA & YOUTUBE UPLOAD
# ============================================================

def save_metadata(data):
    hashtags = []
    for h in data.get("hashtags", []):
        h = str(h).strip()
        if h and not h.startswith("#"):
            h = "#" + h
        if h:
            hashtags.append(h)

    description = clean(data.get("description", ""))
    hashtag_text = " ".join(hashtags)
    if hashtag_text and hashtag_text not in description:
        description += "\n\n" + hashtag_text

    metadata = {
        "title": clean(data["title"]),
        "description": description,
        "hashtags": hashtags,
        "tags": data.get("tags", []),
        "topic": clean(data["topic"])
    }

    (BASE / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    return metadata


def youtube_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    data = json.loads(YOUTUBE_TOKEN_JSON)
    if "installed" in data or "web" in data:
        raise RuntimeError("YOUTUBE_TOKEN_JSON is OAuth client secret, not authorized token JSON.")

    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes", ["https://www.googleapis.com/auth/youtube.upload"])
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds.valid:
        raise RuntimeError("YouTube token is invalid.")

    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(service, video, metadata, thumbnail=None, short=False):
    from googleapiclient.http import MediaFileUpload

    title = metadata["title"]
    if short and "#Shorts" not in title:
        title += " #Shorts"

    tags = []
    for tag in metadata.get("tags", []):
        tag = str(tag).replace("#", "").strip()
        if tag and tag not in tags:
            tags.append(tag)

    body = {
        "snippet": {
            "title": title[:100],
            "description": metadata["description"][:5000],
            "tags": tags[:30],
            "categoryId": "28"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    print("\nUPLOADING:", title)
    media = MediaFileUpload(str(video), mimetype="video/mp4", resumable=True, chunksize=8 * 1024 * 1024)
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"UPLOAD: {int(status.progress() * 100)}%")

    video_id = response["id"]

    if thumbnail and not short:
        service.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail), mimetype="image/jpeg")
        ).execute()

    print("YOUTUBE ID:", video_id)
    return video_id


# ============================================================
# MAIN
# ============================================================

def main():
    print("\n====================================")
    print(" TECHMIND STUDIO AUTO PUBLISHER")
    print("====================================\n")

    data = create_content()
    print("\nTOPIC:", data["topic"])
    print("\nTITLE:", data["title"])

    metadata = save_metadata(data)

    print("\nCREATING LONG VIDEO...")
    long_video = create_long(data)

    print("\nCREATING SHORT...")
    short_video = create_short(data)

    print("\nCREATING THUMBNAIL...")
    thumbnail = create_thumbnail(data)

    print("\nCONNECTING TO YOUTUBE...")
    service = youtube_service()

    long_id = upload(service, long_video, metadata, thumbnail=thumbnail, short=False)
    short_id = upload(service, short_video, metadata, thumbnail=None, short=True)

    result = {
        "title": metadata["title"],
        "topic": metadata["topic"],
        "long_video": str(long_video),
        "short_video": str(short_video),
        "thumbnail": str(thumbnail),
        "long_video_id": long_id,
        "short_video_id": short_id,
        "long_url": f"https://youtube.com/watch?v={long_id}",
        "short_url": f"https://youtube.com/watch?v={short_id}"
    }

    (BASE / "youtube_upload.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("\n====================================")
    print(" SUCCESS — TECHMIND STUDIO")
    print("====================================")
    print("\nLONG:", result["long_url"])
    print("SHORT:", result["short_url"])


if __name__ == "__main__":
    main()
