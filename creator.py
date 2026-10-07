# ============================================================
# TECHMIND STUDIO - AUTOMATIC AI YOUTUBE PUBLISHER
# MAX 3 MINUTES + RELEVANT VISUALS + ANIMATION
# ============================================================

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

MAX_LONG_SECONDS = 180
TARGET_LONG_SECONDS = 170

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing")

if not YOUTUBE_TOKEN_JSON:
    raise RuntimeError("YOUTUBE_TOKEN_JSON is missing")


# ============================================================
# BASIC HELPERS
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
        raise RuntimeError(
            f"Command failed with exit code {p.returncode}"
        )

    return p


def clean_text(s):
    s = str(s or "")
    s = re.sub(r"```(?:json)?", "", s, flags=re.I)
    s = s.replace("```", "")
    return s.strip()


def get_duration(path):
    p = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path)
        ],
        capture_output=True,
        text=True,
        check=True
    )

    return float(p.stdout.strip())


# ============================================================
# GEMINI
# ============================================================

def gemini(prompt, retries=5):

    models = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash"
    ]

    last_error = ""

    for attempt in range(1, retries + 1):

        for model in models:

            url = (
                "https://generativelanguage.googleapis.com/"
                f"v1beta/models/{model}:generateContent"
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
                    "temperature": 0.8,
                    "maxOutputTokens": 8192
                }
            }

            try:

                response = requests.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": GEMINI_API_KEY
                    },
                    json=payload,
                    timeout=120
                )

                print(
                    f"Gemini {model}: "
                    f"HTTP {response.status_code}"
                )

                if response.status_code == 200:

                    data = response.json()

                    candidates = data.get(
                        "candidates",
                        []
                    )

                    if not candidates:
                        continue

                    parts = candidates[0].get(
                        "content",
                        {}
                    ).get(
                        "parts",
                        []
                    )

                    text = "".join(
                        part.get("text", "")
                        for part in parts
                        if "text" in part
                    )

                    text = clean_text(text)

                    if text:
                        return text

                elif response.status_code == 404:
                    continue

                elif response.status_code in [
                    429,
                    500,
                    502,
                    503,
                    504
                ]:
                    last_error = response.text

                else:
                    raise RuntimeError(
                        "Gemini HTTP "
                        f"{response.status_code}: "
                        f"{response.text[:500]}"
                    )

            except requests.RequestException as e:
                last_error = str(e)

        wait = min(20, attempt * 4)

        print(
            f"Gemini retry in {wait} seconds..."
        )

        time.sleep(wait)

    raise RuntimeError(
        "Gemini failed after retries: "
        + str(last_error)
    )


# ============================================================
# CONTENT CREATION
# ============================================================

def create_content():

    prompt = f"""
You are the senior producer for {CHANNEL}.

Create ONE fresh and interesting AI/technology YouTube topic.

IMPORTANT VIDEO LENGTH:
The LONG video must be MAXIMUM 3 MINUTES.
Target approximately 2 minutes 40 seconds to 2 minutes 55 seconds.

Use approximately 380-440 spoken words total.

Create EXACTLY 8 long-video scenes.

Each scene must have:
1. narration
2. visual_query

The narration must be concise so the total finished video stays below 3 minutes.

VISUAL REQUIREMENT:
Every scene must have a highly specific visual_query describing
exactly what should be visible for that scene.

DO NOT use generic queries such as:
"artificial intelligence"
"technology"
"robot"

Instead use specific searches such as:
"OpenAI AI assistant computer interface"
"AI coding assistant developer laptop"
"autonomous AI agent workflow diagram"
"AI customer service chatbot office"

The visual_query must match the narration of THAT scene.

LONG VIDEO:
- strong hook in first 5-8 seconds
- natural conversational English
- useful information
- practical examples
- no fake claims
- no repetitive filler
- fast pacing
- strong ending
- exactly 8 scenes
- approximately 45-55 words per scene

Also create a 40-55 second YouTube Short.
Use exactly 4 scenes.
Each Short scene must also have a highly specific visual_query.

TITLE:
- under 90 characters
- clickable but truthful
- include 1 or 2 relevant AI/technology emojis

DESCRIPTION:
- professional
- summarize the video
- include hashtags

TAGS:
- 12 to 15 relevant YouTube tags

Return ONLY valid JSON.

JSON format:

{{
  "topic": "...",
  "title": "...",
  "description": "...",
  "hashtags": [
    "#AI",
    "#ArtificialIntelligence",
    "#Technology"
  ],
  "tags": [
    "AI",
    "artificial intelligence"
  ],
  "long_scenes": [
    {{
      "narration": "...",
      "visual_query": "very specific visual search query"
    }}
  ],
  "short_scenes": [
    {{
      "narration": "...",
      "visual_query": "very specific visual search query"
    }}
  ]
}}
"""

    raw = gemini(prompt)

    start = raw.find("{")
    end = raw.rfind("}")

    if start < 0 or end < 0:
        raise RuntimeError(
            "Gemini returned invalid JSON"
        )

    data = json.loads(
        raw[start:end + 1]
    )

    if len(data.get("long_scenes", [])) < 8:
        raise RuntimeError(
            "Gemini did not create 8 long scenes"
        )

    if len(data.get("short_scenes", [])) < 4:
        raise RuntimeError(
            "Gemini did not create 4 Short scenes"
        )

    data["long_scenes"] = data[
        "long_scenes"
    ][:8]

    data["short_scenes"] = data[
        "short_scenes"
    ][:4]

    return data


# ============================================================
# VOICE
# ============================================================

def make_voice(text, output):

    run(
        [
            "edge-tts",
            "--voice",
            VOICE,
            "--rate=-5%",
            "--text",
            text,
            "--write-media",
            str(output)
        ]
    )

    if not output.exists():
        raise RuntimeError(
            "Voice file was not created"
        )


# ============================================================
# FRESH RELEVANT IMAGE SEARCH
# ============================================================

def search_wikimedia(query):

    response = requests.get(
        "https://commons.wikimedia.org/w/api.php",
        params={
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": 30,
            "prop": "imageinfo",
            "iiprop": "url|size",
            "iiurlwidth": 2200
        },
        headers={
            "User-Agent": "TechMindStudio/2.0"
        },
        timeout=40
    )

    response.raise_for_status()

    pages = (
        response.json()
        .get("query", {})
        .get("pages", {})
    )

    results = []

    for page in pages.values():

        info = page.get(
            "imageinfo",
            []
        )

        if not info:
            continue

        item = info[0]

        url = (
            item.get("thumburl")
            or item.get("url")
        )

        if url:
            results.append(url)

    return results


def download_image(query, output):

    print(
        "\n================================================"
    )
    print("SCENE VISUAL SEARCH:")
    print(query)
    print(
        "================================================"
    )

    urls = search_wikimedia(query)

    if not urls:
        raise RuntimeError(
            "No relevant image found for: "
            + query
        )

    random.shuffle(urls)

    for url in urls:

        try:

            response = requests.get(
                url,
                headers={
                    "User-Agent":
                    "TechMindStudio/2.0"
                },
                timeout=60
            )

            response.raise_for_status()

            content = response.content

            if len(content) < 30000:
                continue

            output.write_bytes(content)

            print(
                "RELEVANT IMAGE DOWNLOADED:",
                output
            )

            return

        except Exception as e:

            print(
                "Image failed:",
                e
            )

    raise RuntimeError(
        "No usable image found for query: "
        + query
    )


# ============================================================
# ATTRACTIVE SCENE VIDEO
# ============================================================

def make_scene(
    image,
    audio,
    output,
    motion,
    scene_number
):

    scene_duration = get_duration(audio)

    # Different animation for every scene.
    if motion == "left":

        zoom = "1.08+0.00035*on"

        x = (
            "(iw-iw/zoom)*"
            "(0.15+0.70*on/(30*"
            f"{scene_duration}"))"
        )

        y = (
            "ih/2-(ih/zoom/2)"
        )

    elif motion == "right":

        zoom = "1.08+0.00035*on"

        x = (
            "(iw-iw/zoom)*"
            "(0.85-0.70*on/(30*"
            f"{scene_duration}"))"
        )

        y = (
            "ih/2-(ih/zoom/2)"
        )

    elif motion == "up":

        zoom = "1.07+0.00030*on"

        x = (
            "iw/2-(iw/zoom/2)"
        )

        y = (
            "(ih-ih/zoom)*"
            "(0.80-0.60*on/(30*"
            f"{scene_duration}"))"
        )

    elif motion == "down":

        zoom = "1.07+0.00030*on"

        x = (
            "iw/2-(iw/zoom/2)"
        )

        y = (
            "(ih-ih/zoom)*"
            "(0.20+0.60*on/(30*"
            f"{scene_duration}"))"
        )

    elif motion == "zoom_out":

        zoom = (
            "1.20-"
            "0.00030*on"
        )

        x = (
            "iw/2-(iw/zoom/2)"
        )

        y = (
            "ih/2-(ih/zoom/2)"
        )

    else:

        zoom = (
            "1.02+"
            "0.00045*on"
        )

        x = (
            "iw/2-(iw/zoom/2)"
        )

        y = (
            "ih/2-(ih/zoom/2)"
        )

    vf = (
        "scale=2200:1240:"
        "force_original_aspect_ratio=increase,"
        "crop=2200:1240,"
        "zoompan="
        f"z='{zoom}':"
        f"x='{x}':"
        f"y='{y}':"
        "d=1:"
        "s=1920x1080:"
        "fps=30,"
        "format=yuv420p"
    )

    run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image),
            "-i",
            str(audio),
            "-vf",
            vf,
            "-t",
            str(scene_duration),
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "19",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output)
        ]
    )


# ============================================================
# LONG VIDEO
# ============================================================

def create_long(data):

    scenes = data["long_scenes"]

    videos = []

    motions = [
        "left",
        "right",
        "up",
        "down",
        "zoom_out",
        "zoom",
        "left",
        "right"
    ]

    for index, scene in enumerate(scenes):

        number = index + 1

        print(
            f"\n========== LONG SCENE "
            f"{number}/{len(scenes)} =========="
        )

        narration = str(
            scene["narration"]
        ).strip()

        visual_query = str(
            scene["visual_query"]
        ).strip()

        audio = (
            AUDIO /
            f"long_{number:02d}.mp3"
        )

        image = (
            LONG /
            f"scene_{number:02d}.jpg"
        )

        video = (
            LONG /
            f"scene_{number:02d}.mp4"
        )

        make_voice(
            narration,
            audio
        )

        # IMPORTANT:
        # Every scene gets its own fresh
        # topic-specific image search.
        download_image(
            visual_query,
            image
        )

        make_scene(
            image,
            audio,
            video,
            motions[index % len(motions)],
            number
        )

        videos.append(video)

    # --------------------------------------------------------
    # CONCAT
    # --------------------------------------------------------

    concat = LONG / "concat.txt"

    with concat.open(
        "w",
        encoding="utf-8"
    ) as file:

        for video in videos:

            file.write(
                f"file '{video.resolve()}'\n"
            )

    raw = LONG / "raw_long.mp4"

    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(raw)
        ]
    )

    # --------------------------------------------------------
    # FINAL 3-MINUTE LIMIT
    # --------------------------------------------------------

    final = LONG / "final_long.mp4"

    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(raw),
            "-t",
            str(MAX_LONG_SECONDS),
            "-vf",
            (
                "drawtext="
                "fontfile=/usr/share/fonts/"
                "truetype/dejavu/"
                "DejaVuSans-Bold.ttf:"
                "fontcolor=white@0.82:"
                "fontsize=34:"
                "text='TechMind Studio':"
                "x=45:"
                "y=h-th-35:"
                "shadowcolor=black@0.7:"
                "shadowx=2:"
                "shadowy=2"
            ),
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
            "-movflags",
            "+faststart",
            str(final)
        ]
    )

    final_duration = get_duration(final)

    print(
        "\nFINAL LONG VIDEO LENGTH:",
        round(final_duration, 2),
        "seconds"
    )

    if final_duration > MAX_LONG_SECONDS + 1:
        raise RuntimeError(
            "Long video exceeded 3 minute limit"
        )

    return final


# ============================================================
# SHORT
# ============================================================

def create_short(data):

    scenes = data["short_scenes"]

    videos = []

    motions = [
        "zoom",
        "left",
        "right",
        "down"
    ]

    for index, scene in enumerate(scenes):

        number = index + 1

        audio = (
            AUDIO /
            f"short_{number:02d}.mp3"
        )

        image = (
            SHORT /
            f"scene_{number:02d}.jpg"
        )

        video = (
            SHORT /
            f"scene_{number:02d}.mp4"
        )

        make_voice(
            scene["narration"],
            audio
        )

        download_image(
            scene["visual_query"],
            image
        )

        d = get_duration(audio)

        if motions[index] == "left":

            zoom = "1.08+0.0004*on"
            x = "(iw-iw/zoom)*0.7"
            y = "ih/2-(ih/zoom/2)"

        elif motions[index] == "right":

            zoom = "1.08+0.0004*on"
            x = "(iw-iw/zoom)*0.3"
            y = "ih/2-(ih/zoom/2)"

        elif motions[index] == "down":

            zoom = "1.07+0.00035*on"
            x = "iw/2-(iw/zoom/2)"
            y = "(ih-ih/zoom)*0.7"

        else:

            zoom = "1.03+0.00045*on"
            x = "iw/2-(iw/zoom/2)"
            y = "ih/2-(ih/zoom/2)"

        vf = (
            "scale=1080:1920:"
            "force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "zoompan="
            f"z='{zoom}':"
            f"x='{x}':"
            f"y='{y}':"
            "d=1:"
            "s=1080x1920:"
            "fps=30,"
            "format=yuv420p"
        )

        run(
            [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-i",
                str(image),
                "-i",
                str(audio),
                "-vf",
                vf,
                "-t",
                str(d),
                "-r",
                "30",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                "-shortest",
                "-movflags",
                "+faststart",
                str(video)
            ]
        )

        videos.append(video)

    concat = SHORT / "concat.txt"

    with concat.open(
        "w",
        encoding="utf-8"
    ) as file:

        for video in videos:

            file.write(
                f"file '{video.resolve()}'\n"
            )

    raw = SHORT / "raw_short.mp4"

    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(raw)
        ]
    )

    final = SHORT / "final_short.mp4"

    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(raw),
            "-vf",
            (
                "drawtext="
                "fontfile=/usr/share/fonts/"
                "truetype/dejavu/"
                "DejaVuSans-Bold.ttf:"
                "fontcolor=white@0.85:"
                "fontsize=38:"
                "text='TechMind Studio':"
                "x=35:"
                "y=h-th-45:"
                "shadowcolor=black@0.7:"
                "shadowx=2:"
                "shadowy=2"
            ),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "19",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(final)
        ]
    )

    return final


# ============================================================
# THUMBNAIL
# ============================================================

def create_thumbnail(data):

    source = THUMB / "source.jpg"

    query = (
        data["topic"]
        + " artificial intelligence "
        + "technology professional"
    )

    download_image(
        query,
        source
    )

    thumbnail = THUMB / "thumbnail.jpg"

    title = str(
        data.get(
            "title",
            "AI Technology"
        )
    )

    # Remove characters that can cause
    # FFmpeg drawtext problems.
    title = re.sub(
        r"[^A-Za-z0-9 .,!?&-]",
        "",
        title
    )

    title = title.replace(
        ":",
        ""
    )

    title = title[:55]

    drawtext = (
        "drawtext="
        "fontfile=/usr/share/fonts/"
        "truetype/dejavu/"
        "DejaVuSans-Bold.ttf:"
        "fontcolor=white:"
        "fontsize=62:"
        f"text='{title}':"
        "x=60:"
        "y=70:"
        "borderw=4:"
        "bordercolor=black"
    )

    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-vf",
            (
                "scale=1280:720:"
                "force_original_aspect_ratio=increase,"
                "crop=1280:720,"
                + drawtext
            ),
            "-q:v",
            "2",
            str(thumbnail)
        ]
    )

    return thumbnail


# ============================================================
# METADATA
# ============================================================

def save_metadata(data):

    metadata = {
        "channel": CHANNEL,
        "title": data.get("title", ""),
        "description": data.get(
            "description",
            ""
        ),
        "hashtags": data.get(
            "hashtags",
            []
        ),
        "tags": data.get(
            "tags",
            []
        )
    }

    hashtags = metadata["hashtags"]

    if hashtags:

        metadata["description"] += (
            "\n\n"
            + " ".join(hashtags)
        )

    path = BASE / "metadata.json"

    path.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    return metadata


# ============================================================
# YOUTUBE UPLOAD
# ============================================================

def youtube_service():

    from google.oauth2.credentials import (
        Credentials
    )

    from googleapiclient.discovery import (
        build
    )

    token = json.loads(
        YOUTUBE_TOKEN_JSON
    )

    credentials = Credentials.from_authorized_user_info(
        token,
        scopes=[
            "https://www.googleapis.com/auth/youtube.upload"
        ]
    )

    return build(
        "youtube",
        "v3",
        credentials=credentials
    )


def upload_video(
    service,
    video_path,
    title,
    description,
    tags,
    category="28"
):

    from googleapiclient.http import (
        MediaFileUpload
    )

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True
    )

    request = service.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = request.execute()

    video_id = response["id"]

    print(
        "\nYOUTUBE UPLOADED:",
        video_id
    )

    return video_id


def upload_thumbnail(
    service,
    video_id,
    thumbnail
):

    from googleapiclient.http import (
        MediaFileUpload
    )

    media = MediaFileUpload(
        str(thumbnail),
        mimetype="image/jpeg"
    )

    service.thumbnails().set(
        videoId=video_id,
        media_body=media
    ).execute()

    print(
        "THUMBNAIL UPLOADED"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "\n=========================================="
    )

    print(
        "TECHMIND STUDIO AUTOMATION STARTED"
    )

    print(
        "MAX LONG VIDEO: 3 MINUTES"
    )

    print(
        "SCENE-SPECIFIC FRESH VISUALS: ON"
    )

    print(
        "==========================================\n"
    )

    data = create_content()

    print(
        "\nTOPIC:",
        data.get("topic")
    )

    print(
        "TITLE:",
        data.get("title")
    )

    metadata = save_metadata(data)

    long_video = create_long(data)

    short_video = create_short(data)

    thumbnail = create_thumbnail(data)

    service = youtube_service()

    long_id = upload_video(
        service,
        long_video,
        metadata["title"],
        metadata["description"],
        metadata["tags"]
    )

    upload_thumbnail(
        service,
        long_id,
        thumbnail
    )

    short_title = (
        metadata["title"]
        + " #Shorts"
    )

    short_description = (
        metadata["description"]
        + "\n\n#Shorts"
    )

    upload_video(
        service,
        short_video,
        short_title,
        short_description,
        metadata["tags"]
    )

    print(
        "\n=========================================="
    )

    print(
        "ALL DONE - TECHMIND STUDIO"
    )

    print(
        "Long video:",
        long_video
    )

    print(
        "Short:",
        short_video
    )

    print(
        "Thumbnail:",
        thumbnail
    )

    print(
        "=========================================="
    )


if __name__ == "__main__":
    main()
