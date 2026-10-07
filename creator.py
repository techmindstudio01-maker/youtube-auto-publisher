# ============================================================
# TECHMIND STUDIO - FULL AUTOMATIC AI YOUTUBE PUBLISHER
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

# CURRENT GEMINI MODELS
GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
]

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing")

if not YOUTUBE_TOKEN_JSON:
    raise RuntimeError("YOUTUBE_TOKEN_JSON is missing")


# ============================================================
# BASIC HELPERS
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
            f"Command failed with exit code {process.returncode}"
        )

    return process


def get_duration(path):
    result = subprocess.run(
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

    return float(result.stdout.strip())


def clean_text(text):
    text = str(text or "")
    text = text.replace("```json", "")
    text = text.replace("```", "")
    return text.strip()


# ============================================================
# GEMINI
# ============================================================

def gemini(prompt, retries=4):

    last_error = ""

    for attempt in range(1, retries + 1):

        for model in GEMINI_MODELS:

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
                ]
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
                    f"Gemini {model} HTTP {response.status_code}"
                )

                if response.status_code == 200:

                    data = response.json()

                    candidates = data.get(
                        "candidates",
                        []
                    )

                    if not candidates:
                        last_error = "No candidates returned"
                        continue

                    parts = (
                        candidates[0]
                        .get("content", {})
                        .get("parts", [])
                    )

                    output = ""

                    for part in parts:
                        if "text" in part:
                            output += part["text"]

                    output = clean_text(output)

                    if output:
                        return output

                    last_error = "Empty Gemini response"
                    continue

                if response.status_code in [401, 403]:

                    raise RuntimeError(
                        "Gemini API authentication failed: "
                        + response.text[:1000]
                    )

                last_error = response.text[:1000]

            except requests.RequestException as error:

                last_error = str(error)

        wait = min(20, attempt * 4)

        print(
            f"Gemini retry in {wait} seconds..."
        )

        time.sleep(wait)

    raise RuntimeError(
        "Gemini failed after retries: "
        + last_error
    )


# ============================================================
# CONTENT CREATION
# ============================================================

def create_content():

    prompt = f"""
You are the senior producer for {CHANNEL}.

Create ONE fresh and useful AI/technology YouTube topic.

IMPORTANT:

The final long video MUST be under 3 minutes.

Target duration:
2 minutes 35 seconds to 2 minutes 55 seconds.

Total spoken words:
330 to 390 words.

Create EXACTLY 8 long-video scenes.

Each long scene must contain:
1. narration
2. visual_query

The visual_query must describe exactly what should appear
on screen for that specific narration.

Do NOT use generic visual queries such as:
"AI robot"
"artificial intelligence"
"technology"

Instead use specific visuals.

Examples:
"developer using GitHub Copilot inside VS Code"
"AI chatbot interface showing code generation"
"smartphone screen displaying an AI image generator"
"business dashboard with AI automation workflow"

LONG VIDEO REQUIREMENTS:

- strong first 5-10 second hook
- natural conversational English
- practical information
- useful examples
- no fake facts
- no repetitive filler
- strong ending
- every scene visually different
- each scene must directly match its narration

SHORT:

Create EXACTLY 4 scenes.

Short duration:
40 to 55 seconds.

Short must have:
- fast hook
- useful information
- scene-specific visuals
- vertical-video friendly ideas

TITLE:

- under 90 characters
- clickable but truthful
- include 1 or 2 relevant AI/technology emojis

DESCRIPTION:

- professional
- useful
- include CTA
- include hashtags

TAGS:

Create 12 to 15 YouTube tags.

Return ONLY valid JSON.

JSON FORMAT:

{{
    "topic": "...",
    "title": "...",
    "description": "...",
    "hashtags": [
        "#AI",
        "#Technology"
    ],
    "tags": [
        "AI",
        "artificial intelligence"
    ],
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
            "Gemini returned fewer than 8 long scenes"
        )

    if len(short_scenes) < 4:
        raise RuntimeError(
            "Gemini returned fewer than 4 short scenes"
        )

    data["long_scenes"] = long_scenes[:8]
    data["short_scenes"] = short_scenes[:4]

    return data


# ============================================================
# EDGE TTS
# ============================================================

def create_voice(text, output):

    run([
        "edge-tts",
        "--voice",
        VOICE,
        "--rate=-5%",
        "--text",
        text,
        "--write-media",
        str(output)
    ])

    if not output.exists():
        raise RuntimeError(
            "Voice file was not created"
        )


# ============================================================
# WIKIMEDIA SEARCH
# ============================================================

def find_images(query):

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

        item = info[0]

        url = (
            item.get("thumburl")
            or item.get("url")
        )

        if url:
            urls.append(url)

    return urls


def download_image(query, output):

    print("\nIMAGE SEARCH:")
    print(query)

    urls = find_images(query)

    random.shuffle(urls)

    for url in urls:

        try:

            response = requests.get(
                url,
                timeout=60,
                headers={
                    "User-Agent":
                    "TechMindStudio/1.0"
                }
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
        "No usable image found for query: "
        + query
    )


# ============================================================
# SCENE VIDEO
# ============================================================

def make_scene(
    image,
    audio,
    output,
    motion
):

    audio_duration = get_duration(
        audio
    )

    if motion == "left":

        x = (
            "(iw-iw/zoom)*"
            "(0.5+0.35*sin(on/180))"
        )

        y = (
            "ih/2-(ih/zoom/2)"
        )

        z = "1.05"

    elif motion == "right":

        x = (
            "(iw-iw/zoom)*"
            "(0.5-0.35*sin(on/180))"
        )

        y = (
            "ih/2-(ih/zoom/2)"
        )

        z = "1.05"

    elif motion == "up":

        x = (
            "iw/2-(iw/zoom/2)"
        )

        y = (
            "(ih-ih/zoom)*"
            "(0.5-0.35*sin(on/180))"
        )

        z = "1.05"

    elif motion == "down":

        x = (
            "iw/2-(iw/zoom/2)"
        )

        y = (
            "(ih-ih/zoom)*"
            "(0.5+0.35*sin(on/180))"
        )

        z = "1.05"

    else:

        x = (
            "iw/2-(iw/zoom/2)"
        )

        y = (
            "ih/2-(ih/zoom/2)"
        )

        z = "1.02+0.00008*on"

    video_filter = (
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
        "-loop",
        "1",
        "-i",
        str(image),
        "-i",
        str(audio),
        "-vf",
        video_filter,
        "-t",
        str(audio_duration),
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
    ])


# ============================================================
# CONCAT
# ============================================================

def concat_videos(
    videos,
    output
):

    list_file = output.with_suffix(
        ".txt"
    )

    with list_file.open(
        "w",
        encoding="utf-8"
    ) as file:

        for video in videos:

            file.write(
                f"file '{video.resolve()}'\n"
            )

    run([
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output)
    ])


# ============================================================
# LONG VIDEO
# ============================================================

def create_long(data):

    videos = []

    motions = [
        "zoom",
        "left",
        "right",
        "up",
        "down",
        "zoom",
        "left",
        "right"
    ]

    scenes = data[
        "long_scenes"
    ][:8]

    for index, scene in enumerate(
        scenes,
        start=1
    ):

        print(
            f"\n===== LONG SCENE "
            f"{index}/8 ====="
        )

        audio = (
            AUDIO /
            f"long_{index:02d}.mp3"
        )

        image = (
            LONG /
            f"scene_{index:02d}.jpg"
        )

        video = (
            LONG /
            f"scene_{index:02d}.mp4"
        )

        create_voice(
            scene["narration"],
            audio
        )

        download_image(
            scene["visual_query"],
            image
        )

        make_scene(
            image,
            audio,
            video,
            motions[index - 1]
        )

        videos.append(video)

    raw = LONG / "raw_long.mp4"

    concat_videos(
        videos,
        raw
    )

    final = LONG / "final_long.mp4"

    watermark = (
        "drawtext="
        "fontfile=/usr/share/fonts/"
        "truetype/dejavu/"
        "DejaVuSans-Bold.ttf:"
        "fontcolor=white@0.80:"
        "fontsize=34:"
        "text='TechMind Studio':"
        "x=45:"
        "y=h-th-35:"
        "shadowcolor=black@0.7:"
        "shadowx=2:"
        "shadowy=2"
    )

    run([
        "ffmpeg",
        "-y",
        "-i",
        str(raw),
        "-t",
        "180",
        "-vf",
        watermark,
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
    ])

    final_duration = get_duration(
        final
    )

    print(
        "FINAL LONG DURATION:",
        final_duration
    )

    if final_duration > 180.5:
        raise RuntimeError(
            "Long video exceeded 180 seconds"
        )

    return final


# ============================================================
# SHORT
# ============================================================

def create_short(data):

    videos = []

    scenes = data[
        "short_scenes"
    ][:4]

    for index, scene in enumerate(
        scenes,
        start=1
    ):

        audio = (
            AUDIO /
            f"short_{index:02d}.mp3"
        )

        image = (
            SHORT /
            f"scene_{index:02d}.jpg"
        )

        video = (
            SHORT /
            f"scene_{index:02d}.mp4"
        )

        create_voice(
            scene["narration"],
            audio
        )

        download_image(
            scene["visual_query"],
            image
        )

        audio_duration = get_duration(
            audio
        )

        video_filter = (
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
            "-loop",
            "1",
            "-i",
            str(image),
            "-i",
            str(audio),
            "-vf",
            video_filter,
            "-t",
            str(audio_duration),
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
        ])

        videos.append(video)

    raw = SHORT / "raw_short.mp4"

    concat_videos(
        videos,
        raw
    )

    final = SHORT / "final_short.mp4"

    watermark = (
        "drawtext="
        "fontfile=/usr/share/fonts/"
        "truetype/dejavu/"
        "DejaVuSans-Bold.ttf:"
        "fontcolor=white@0.82:"
        "fontsize=38:"
        "text='TechMind Studio':"
        "x=35:"
        "y=h-th-45:"
        "shadowcolor=black@0.7:"
        "shadowx=2:"
        "shadowy=2"
    )

    run([
        "ffmpeg",
        "-y",
        "-i",
        str(raw),
        "-vf",
        watermark,
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
    ])

    return final


# ============================================================
# THUMBNAIL
# ============================================================

def clean_title_for_ffmpeg(title):

    title = str(title)

    title = re.sub(
        r"[^A-Za-z0-9 .,!?()\-:&+]",
        "",
        title
    )

    title = title.replace(
        "'",
        ""
    )

    return title[:85]


def create_thumbnail(data):

    source = (
        THUMB /
        "source.jpg"
    )

    download_image(
        data["topic"]
        + " artificial intelligence technology professional",
        source
    )

    output = (
        THUMB /
        "thumbnail.jpg"
    )

    title = clean_title_for_ffmpeg(
        data.get(
            "title",
            "AI Technology"
        )
    )

    video_filter = (
        "scale=1280:720:"
        "force_original_aspect_ratio=increase,"
        "crop=1280:720,"
        "drawtext="
        "fontfile=/usr/share/fonts/"
        "truetype/dejavu/"
        "DejaVuSans-Bold.ttf:"
        "fontcolor=white:"
        "fontsize=48:"
        f"text='{title}':"
        "x=50:"
        "y=h-th-60:"
        "box=1:"
        "boxcolor=black@0.55:"
        "boxborderw=18"
    )

    run([
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-vf",
        video_filter,
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

def make_metadata(data):

    hashtags = data.get(
        "hashtags",
        []
    )

    description = str(
        data.get(
            "description",
            ""
        )
    ).strip()

    for hashtag in hashtags:

        if hashtag not in description:

            description += (
                "\n" +
                hashtag
            )

    title = str(
        data.get(
            "title",
            "AI Technology"
        )
    ).strip()

    return {
        "title": title[:90],
        "description": description,
        "tags": [
            str(tag)[:30]
            for tag in data.get(
                "tags",
                []
            )
        ][:15]
    }


# ============================================================
# YOUTUBE
# ============================================================

def youtube_service():

    from google.oauth2.credentials import (
        Credentials
    )

    from googleapiclient.discovery import (
        build
    )

    info = json.loads(
        YOUTUBE_TOKEN_JSON
    )

    credentials = (
        Credentials
        .from_authorized_user_info(
            info,
            scopes=[
                "https://www.googleapis.com/"
                "auth/youtube.upload"
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
    metadata
):

    from googleapiclient.http import (
        MediaFileUpload
    )

    body = {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata["tags"],
            "categoryId": "28"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(
        str(video_path),
        chunksize=-1,
        resumable=True
    )

    request = (
        service.videos()
        .insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
    )

    response = None

    while response is None:

        _, response = (
            request.next_chunk()
        )

        if response:
            print(
                "UPLOAD RESPONSE:",
                response
            )

    return response["id"]


def upload_thumbnail(
    service,
    video_id,
    thumbnail_path
):

    from googleapiclient.http import (
        MediaFileUpload
    )

    media = MediaFileUpload(
        str(thumbnail_path),
        mimetype="image/jpeg"
    )

    service.thumbnails().set(
        videoId=video_id,
        media_body=media
    ).execute()


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 50)
    print("TECHMIND STUDIO AUTOMATION")
    print("=" * 50)
    print("GEMINI: 3.8 FLASH")
    print("MAX LONG VIDEO: 180 SECONDS")
    print("SCENE-SPECIFIC VISUALS: ENABLED")
    print("ANIMATED VISUALS: ENABLED")
    print("SHORTS: ENABLED")
    print("THUMBNAIL: ENABLED")
    print("=" * 50)

    data = create_content()

    metadata = make_metadata(
        data
    )

    print(
        "\nTITLE:",
        metadata["title"]
    )

    print(
        "\nTOPIC:",
        data["topic"]
    )

    long_video = create_long(
        data
    )

    short_video = create_short(
        data
    )

    thumbnail = create_thumbnail(
        data
    )

    service = youtube_service()

    long_id = upload_video(
        service,
        long_video,
        metadata
    )

    print(
        "\nLONG VIDEO UPLOADED:",
        long_id
    )

    upload_thumbnail(
        service,
        long_id,
        thumbnail
    )

    print(
        "THUMBNAIL UPLOADED"
    )

    short_metadata = dict(
        metadata
    )

    short_metadata["title"] = (
        metadata["title"][:80]
        + " #Shorts"
    )

    short_metadata["description"] = (
        metadata["description"]
        + "\n#Shorts"
    )

    short_id = upload_video(
        service,
        short_video,
        short_metadata
    )

    print(
        "\nSHORT UPLOADED:",
        short_id
    )

    print("=" * 50)
    print("TECHMIND STUDIO AUTOMATION COMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    main()
