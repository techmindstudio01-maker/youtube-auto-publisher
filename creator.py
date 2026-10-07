# ============================================================
# TECHMIND STUDIO - AUTOMATIC AI YOUTUBE PUBLISHER
# MAX 3 MIN LONG VIDEO
# SCENE-SPECIFIC VISUALS + ANIMATION + SHORT + THUMBNAIL
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

for folder in [LONG, SHORT, AUDIO, THUMB]:
    folder.mkdir(parents=True, exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
YOUTUBE_TOKEN_JSON = os.getenv("YOUTUBE_TOKEN_JSON", "").strip()

VOICE = "en-US-ChristopherNeural"

MAX_LONG_SECONDS = 180

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing")

if not YOUTUBE_TOKEN_JSON:
    raise RuntimeError("YOUTUBE_TOKEN_JSON is missing")


# ============================================================
# COMMAND HELPER
# ============================================================

def run(cmd):
    print("\nRUN:", " ".join(map(str, cmd)))

    process = subprocess.run(
        [str(x) for x in cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    print(process.stdout)

    if process.returncode != 0:
        raise RuntimeError(
            "Command failed with exit code "
            + str(process.returncode)
        )

    return process


# ============================================================
# DURATION
# ============================================================

def get_duration(path):
    process = subprocess.run(
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

    return float(process.stdout.strip())


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(text):
    text = str(text or "")
    text = re.sub(
        r"```(?:json)?",
        "",
        text,
        flags=re.I
    )
    text = text.replace("```", "")
    return text.strip()


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
                "v1beta/models/"
                + model
                + ":generateContent"
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
                    "Gemini",
                    model,
                    "HTTP",
                    response.status_code
                )

                if response.status_code == 200:

                    result = response.json()

                    candidates = result.get(
                        "candidates",
                        []
                    )

                    if not candidates:
                        continue

                    parts = (
                        candidates[0]
                        .get("content", {})
                        .get("parts", [])
                    )

                    text = ""

                    for part in parts:
                        if "text" in part:
                            text += part["text"]

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
                        + str(response.status_code)
                        + ": "
                        + response.text[:500]
                    )

            except requests.RequestException as error:

                last_error = str(error)

        wait = min(20, attempt * 4)

        print(
            "Gemini retry in",
            wait,
            "seconds..."
        )

        time.sleep(wait)

    raise RuntimeError(
        "Gemini failed after retries: "
        + last_error
    )


# ============================================================
# CONTENT GENERATION
# ============================================================

def create_content():

    prompt = f"""
You are the senior producer for {CHANNEL}.

Create ONE fresh AI or technology YouTube topic.

IMPORTANT:
The LONG VIDEO MUST be MAXIMUM 3 MINUTES.

Target:
2 minutes 35 seconds to 2 minutes 55 seconds.

Use approximately 330-390 spoken English words total.

Create EXACTLY 8 long-video scenes.

Each scene MUST contain:
- narration
- visual_query

The visual_query must describe the EXACT visual needed
for that scene.

Do NOT use generic visual queries.

BAD:
"artificial intelligence"
"technology"
"robot"

GOOD:
"AI coding assistant helping developer write code on laptop"
"AI customer service chatbot conversation interface"
"AI video generator creating cinematic video on computer"
"AI agent automating office workflow"

Every scene must have a DIFFERENT visual.

LONG VIDEO:
- powerful first 5 seconds
- natural conversational English
- useful information
- practical examples
- no fake facts
- no filler
- fast pacing
- strong ending
- 8 scenes
- approximately 40-50 spoken words per scene

Also create a YouTube Short.

SHORT:
- 40-55 seconds
- exactly 4 scenes
- fast hook
- useful information
- each scene gets its own specific visual_query

TITLE:
- under 90 characters
- clickable but truthful
- include 1 or 2 relevant AI/technology emojis

DESCRIPTION:
- professional
- useful
- include hashtags

TAGS:
- 12 to 15 YouTube tags

Return ONLY valid JSON.

FORMAT:

{{
  "topic": "...",
  "title": "...",
  "description": "...",
  "hashtags": [
    "#AI",
    "#Technology",
    "#ArtificialIntelligence"
  ],
  "tags": [
    "AI",
    "artificial intelligence",
    "technology"
  ],
  "long_scenes": [
    {{
      "narration": "...",
      "visual_query": "specific visual search query"
    }}
  ],
  "short_scenes": [
    {{
      "narration": "...",
      "visual_query": "specific visual search query"
    }}
  ]
}}
"""

    raw = gemini(prompt)

    start = raw.find("{")
    end = raw.rfind("}")

    if start == -1 or end == -1:
        raise RuntimeError(
            "Gemini returned invalid JSON"
        )

    data = json.loads(
        raw[start:end + 1]
    )

    long_scenes = data.get(
        "long_scenes",
        []
    )

    short_scenes = data.get(
        "short_scenes",
        []
    )

    if len(long_scenes) < 8:
        raise RuntimeError(
            "Gemini created fewer than 8 long scenes"
        )

    if len(short_scenes) < 4:
        raise RuntimeError(
            "Gemini created fewer than 4 short scenes"
        )

    data["long_scenes"] = long_scenes[:8]
    data["short_scenes"] = short_scenes[:4]

    return data


# ============================================================
# EDGE TTS
# ============================================================

def make_voice(text, output):

    run(
        [
            "edge-tts",
            "--voice",
            VOICE,
            "--rate=-5%",
            "--text",
            str(text),
            "--write-media",
            str(output)
        ]
    )

    if not output.exists():
        raise RuntimeError(
            "Voice file was not created"
        )


# ============================================================
# IMAGE SEARCH
# ============================================================

def search_images(query):

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

    urls = []

    for page in pages.values():

        info = page.get(
            "imageinfo",
            []
        )

        if not info:
            continue

        url = (
            info[0].get("thumburl")
            or info[0].get("url")
        )

        if url:
            urls.append(url)

    return urls


def download_image(query, output):

    print("\n----------------------------------------")
    print("VISUAL SEARCH:")
    print(query)
    print("----------------------------------------")

    urls = search_images(query)

    if not urls:
        raise RuntimeError(
            "No image found for: " + query
        )

    random.shuffle(urls)

    for url in urls:

        try:

            response = requests.get(
                url,
                headers={
                    "User-Agent": "TechMindStudio/2.0"
                },
                timeout=60
            )

            response.raise_for_status()

            if len(response.content) < 30000:
                continue

            output.write_bytes(
                response.content
            )

            print(
                "IMAGE OK:",
                output
            )

            return

        except Exception as error:

            print(
                "Image failed:",
                error
            )

    raise RuntimeError(
        "No usable image found for: "
        + query
    )


# ============================================================
# ANIMATED SCENE
# ============================================================

def make_scene(
    image,
    audio,
    output,
    motion
):

    scene_duration = get_duration(
        audio
    )

    # Simple FFmpeg expressions.
    # These are intentionally kept simple
    # to avoid syntax errors.

    if motion == "left":

        zoom = "1.04+0.00020*on"
        x = "0"
        y = "ih/2-(ih/zoom/2)"

    elif motion == "right":

        zoom = "1.04+0.00020*on"
        x = "(iw-iw/zoom)"
        y = "ih/2-(ih/zoom/2)"

    elif motion == "up":

        zoom = "1.04+0.00020*on"
        x = "iw/2-(iw/zoom/2)"
        y = "0"

    elif motion == "down":

        zoom = "1.04+0.00020*on"
        x = "iw/2-(iw/zoom/2)"
        y = "(ih-ih/zoom)"

    elif motion == "zoom_out":

        zoom = "1.18-0.00025*on"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    else:

        zoom = "1.02+0.00025*on"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    vf = (
        "scale=2200:1240:"
        "force_original_aspect_ratio=increase,"
        "crop=2200:1240,"
        "zoompan="
        "z='" + zoom + "':"
        "x='" + x + "':"
        "y='" + y + "':"
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
            "\n========== LONG SCENE "
            + str(number)
            + "/"
            + str(len(scenes))
            + " =========="
        )

        narration = str(
            scene["narration"]
        ).strip()

        visual_query = str(
            scene["visual_query"]
        ).strip()

        audio = (
            AUDIO
            / ("long_%02d.mp3" % number)
        )

        image = (
            LONG
            / ("scene_%02d.jpg" % number)
        )

        video = (
            LONG
            / ("scene_%02d.mp4" % number)
        )

        make_voice(
            narration,
            audio
        )

        # Every scene gets its own
        # specific image search.
        download_image(
            visual_query,
            image
        )

        make_scene(
            image,
            audio,
            video,
            motions[
                index % len(motions)
            ]
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
                "file '"
                + str(video.resolve())
                + "'\n"
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
    # HARD 3-MINUTE LIMIT
    # --------------------------------------------------------

    final = LONG / "final_long.mp4"

    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(raw),
            "-t",
            "180",
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

    final_duration = get_duration(
        final
    )

    print(
        "\nFINAL LONG VIDEO:",
        round(final_duration, 2),
        "seconds"
    )

    if final_duration > 181:
        raise RuntimeError(
            "Video is longer than 3 minutes"
        )

    return final


# ============================================================
# SHORT
# ============================================================

def create_short(data):

    scenes = data["short_scenes"]

    videos = []

    for index, scene in enumerate(scenes):

        number = index + 1

        audio = (
            AUDIO
            / ("short_%02d.mp3" % number)
        )

        image = (
            SHORT
            / ("scene_%02d.jpg" % number)
        )

        video = (
            SHORT
            / ("scene_%02d.mp4" % number)
        )

        make_voice(
            scene["narration"],
            audio
        )

        download_image(
            scene["visual_query"],
            image
        )

        d = get_duration(
            audio
        )

        if index == 0:

            zoom = "1.03+0.00030*on"
            x = "iw/2-(iw/zoom/2)"
            y = "ih/2-(ih/zoom/2)"

        elif index == 1:

            zoom = "1.05+0.00025*on"
            x = "0"
            y = "ih/2-(ih/zoom/2)"

        elif index == 2:

            zoom = "1.05+0.00025*on"
            x = "(iw-iw/zoom)"
            y = "ih/2-(ih/zoom/2)"

        else:

            zoom = "1.04+0.00030*on"
            x = "iw/2-(iw/zoom/2)"
            y = "0"

        vf = (
            "scale=1080:1920:"
            "force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "zoompan="
            "z='" + zoom + "':"
            "x='" + x + "':"
            "y='" + y + "':"
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
                "file '"
                + str(video.resolve())
                + "'\n"
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
        str(data["topic"])
        + " AI technology professional"
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

    title = re.sub(
        r"[^A-Za-z0-9 .,!?&-]",
        "",
        title
    )

    title = title[:55]

    filter_text = (
        "scale=1280:720:"
        "force_original_aspect_ratio=increase,"
        "crop=1280:720,"
        "drawtext="
        "fontfile=/usr/share/fonts/"
        "truetype/dejavu/"
        "DejaVuSans-Bold.ttf:"
        "fontcolor=white:"
        "fontsize=58:"
        "text='"
        + title
        + "':"
        "x=50:"
        "y=60:"
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
            filter_text,
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

    description = str(
        data.get(
            "description",
            ""
        )
    )

    hashtags = data.get(
        "hashtags",
        []
    )

    tags = data.get(
        "tags",
        []
    )

    if hashtags:

        description += (
            "\n\n"
            + " ".join(
                str(x)
                for x in hashtags
            )
        )

    metadata = {
        "channel": CHANNEL,
        "title": str(
            data.get("title", "")
        ),
        "description": description,
        "hashtags": hashtags,
        "tags": tags
    }

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
# YOUTUBE
# ============================================================

def youtube_service():

    from google.oauth2.credentials import Credentials

    from googleapiclient.discovery import build

    token = json.loads(
        YOUTUBE_TOKEN_JSON
    )

    credentials = (
        Credentials
        .from_authorized_user_info(
            token,
            scopes=[
                "https://www.googleapis.com/auth/"
                "youtube.upload"
            ]
        )
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
    tags
):

    from googleapiclient.http import (
        MediaFileUpload
    )

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "28"
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

    result = request.execute()

    video_id = result["id"]

    print(
        "\nYOUTUBE UPLOAD SUCCESS:",
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
        "THUMBNAIL UPLOAD SUCCESS"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n")
    print("==============================================")
    print("TECHMIND STUDIO AUTOMATION")
    print("==============================================")
    print("MAX LONG VIDEO: 180 SECONDS")
    print("SCENE-SPECIFIC VISUALS: ENABLED")
    print("ANIMATED VISUALS: ENABLED")
    print("SHORTS: ENABLED")
    print("THUMBNAIL: ENABLED")
    print("==============================================")
    print("\n")

    # 1. Generate fresh topic/content.
    data = create_content()

    print(
        "\nTOPIC:",
        data.get("topic")
    )

    print(
        "TITLE:",
        data.get("title")
    )

    # 2. Save metadata.
    metadata = save_metadata(
        data
    )

    # 3. Create max 3-minute long video.
    long_video = create_long(
        data
    )

    # 4. Create Short.
    short_video = create_short(
        data
    )

    # 5. Create thumbnail.
    thumbnail = create_thumbnail(
        data
    )

    # 6. Connect YouTube.
    service = youtube_service()

    # 7. Upload long video.
    long_id = upload_video(
        service,
        long_video,
        metadata["title"],
        metadata["description"],
        metadata["tags"]
    )

    # 8. Upload thumbnail.
    upload_thumbnail(
        service,
        long_id,
        thumbnail
    )

    # 9. Upload Short.
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

    print("\n")
    print("==============================================")
    print("TECHMIND STUDIO - ALL DONE")
    print("==============================================")
    print("LONG:", long_video)
    print("SHORT:", short_video)
    print("THUMBNAIL:", thumbnail)
    print("==============================================")


if __name__ == "__main__":
    main()
