import os
import json
import math
import subprocess
import requests
import asyncio
import edge_tts

from PIL import Image, ImageDraw, ImageFont

# ============================================================
# TechMind Studio - Long Video Renderer
# TARGET: 3:15 - 3:45
# STEP 10B
# ============================================================

CONTENT_FILE = "content_package.json"

VIDEO_DIR = "video_assets"
IMAGE_DIR = os.path.join(VIDEO_DIR, "images")
AUDIO_DIR = os.path.join(VIDEO_DIR, "audio")
SCENE_DIR = os.path.join(VIDEO_DIR, "scenes")

OUTPUT_VIDEO = "techmind_studio_long.mp4"

WIDTH = 1280
HEIGHT = 720

TARGET_MIN_SECONDS = 195
TARGET_MAX_SECONDS = 225

VOICE = "en-US-AriaNeural"

os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(SCENE_DIR, exist_ok=True)


# ============================================================
# Utility
# ============================================================

def run_command(command):
    print("Running:", " ".join(command))

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError(
            "Command failed."
        )

    return result


def load_content():
    if not os.path.exists(CONTENT_FILE):
        raise RuntimeError(
            "content_package.json not found."
        )

    with open(
        CONTENT_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        package = json.load(f)

    if not isinstance(package, dict):
        raise RuntimeError(
            "Invalid content_package.json."
        )

    return package


# ============================================================
# Scene recovery
# ============================================================

def build_fallback_scenes(package):

    print(
        "WARNING: No valid scenes found."
    )

    script = package.get(
        "script",
        ""
    ).strip()

    if not script:
        raise RuntimeError(
            "No script available for fallback scenes."
        )

    words = script.split()

    scene_count = 9

    chunk_size = max(
        1,
        math.ceil(
            len(words) / scene_count
        )
    )

    scenes = []

    for i in range(
        0,
        len(words),
        chunk_size
    ):

        chunk = " ".join(
            words[i:i + chunk_size]
        )

        number = len(scenes) + 1

        scenes.append(
            {
                "scene_number": number,
                "heading": f"Scene {number}",
                "narration": chunk,
                "visual_query": package.get(
                    "topic",
                    "artificial intelligence technology"
                ),
                "visual_type": "photo",
                "on_screen_text": ""
            }
        )

    return scenes


def get_scenes(package):

    scenes = package.get(
        "scenes",
        []
    )

    valid = []

    if isinstance(scenes, list):

        for scene in scenes:

            if not isinstance(scene, dict):
                continue

            narration = str(
                scene.get(
                    "narration",
                    ""
                )
            ).strip()

            if not narration:
                continue

            valid.append(
                scene
            )

    if not valid:
        valid = build_fallback_scenes(
            package
        )

    print(
        f"Using {len(valid)} scenes."
    )

    return valid


# ============================================================
# Wikimedia image search
# ============================================================

def search_wikimedia(query):

    url = (
        "https://commons.wikimedia.org/w/api.php"
    )

    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": 8,
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": 1400,
        "format": "json"
    }

    headers = {
        "User-Agent":
        "TechMindStudio-Automation/1.0"
    }

    try:

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        pages = data.get(
            "query",
            {}
        ).get(
            "pages",
            {}
        )

        results = []

        for page in pages.values():

            info = page.get(
                "imageinfo",
                []
            )

            if not info:
                continue

            image_url = info[0].get(
                "thumburl"
            ) or info[0].get(
                "url"
            )

            if image_url:
                results.append(
                    image_url
                )

        return results

    except Exception as e:

        print(
            "Wikimedia search failed:",
            e
        )

        return []


def download_image(
    query,
    output_path,
    scene_index
):

    candidates = search_wikimedia(
        query
    )

    if not candidates:

        print(
            "No Wikimedia image found."
        )

        return create_fallback_image(
            output_path,
            query
        )

    # Rotate through available results
    image_url = candidates[
        (scene_index - 1)
        % len(candidates)
    ]

    headers = {
        "User-Agent":
        "TechMindStudio-Automation/1.0"
    }

    try:

        response = requests.get(
            image_url,
            headers=headers,
            timeout=40
        )

        response.raise_for_status()

        with open(
            output_path,
            "wb"
        ) as f:
            f.write(
                response.content
            )

        return output_path

    except Exception as e:

        print(
            "Image download failed:",
            e
        )

        return create_fallback_image(
            output_path,
            query
        )


# ============================================================
# Fallback image
# ============================================================

def create_fallback_image(
    output_path,
    text
):

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        "black"
    )

    draw = ImageDraw.Draw(
        image
    )

    try:

        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            54
        )

    except Exception:

        font = ImageFont.load_default()

    text = str(text)

    if len(text) > 55:
        text = text[:55] + "..."

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    text_width = (
        bbox[2] - bbox[0]
    )

    text_height = (
        bbox[3] - bbox[1]
    )

    x = (
        WIDTH - text_width
    ) // 2

    y = (
        HEIGHT - text_height
    ) // 2

    draw.text(
        (x, y),
        text,
        fill="white",
        font=font
    )

    image.save(
        output_path,
        quality=95
    )

    return output_path


# ============================================================
# Prepare image
# ============================================================

def prepare_image(
    source_path,
    output_path
):

    try:

        image = Image.open(
            source_path
        ).convert("RGB")

        source_ratio = (
            image.width /
            image.height
        )

        target_ratio = (
            WIDTH /
            HEIGHT
        )

        if source_ratio > target_ratio:

            new_height = HEIGHT

            new_width = int(
                HEIGHT *
                source_ratio
            )

        else:

            new_width = WIDTH

            new_height = int(
                WIDTH /
                source_ratio
            )

        image = image.resize(
            (
                new_width,
                new_height
            ),
            Image.Resampling.LANCZOS
        )

        left = (
            new_width - WIDTH
        ) // 2

        top = (
            new_height - HEIGHT
        ) // 2

        image = image.crop(
            (
                left,
                top,
                left + WIDTH,
                top + HEIGHT
            )
        )

        image.save(
            output_path,
            quality=95
        )

        return output_path

    except Exception as e:

        print(
            "Image processing failed:",
            e
        )

        return create_fallback_image(
            output_path,
            "TechMind Studio"
        )


# ============================================================
# Text to speech
# ============================================================

async def generate_voice(
    text,
    output_path
):

    communicate = edge_tts.Communicate(
        text,
        VOICE,
        rate="-5%"
    )

    await communicate.save(
        output_path
    )


def create_voice(
    text,
    output_path
):

    asyncio.run(
        generate_voice(
            text,
            output_path
        )
    )


# ============================================================
# Get audio duration
# ============================================================

def get_duration(
    file_path
):

    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
    )

    return float(
        result.stdout.strip()
    )


# ============================================================
# Create scene video
# ============================================================

def create_scene_video(
    image_path,
    output_path,
    duration,
    scene_number
):

    duration = max(
        4.0,
        float(duration)
    )

    frames = int(
        duration * 30
    )

    # Alternate zoom direction
    if scene_number % 2 == 0:

        zoom_expr = (
            "min(zoom+0.0007,1.18)"
        )

    else:

        zoom_expr = (
            "min(zoom+0.0005,1.15)"
        )

    filter_complex = (
        f"scale="
        f"{WIDTH * 2}:"
        f"{HEIGHT * 2}:"
        f"force_original_aspect_ratio=increase,"
        f"crop="
        f"{WIDTH * 2}:"
        f"{HEIGHT * 2},"
        f"zoompan="
        f"z='{zoom_expr}':"
        f"x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':"
        f"d={frames}:"
        f"s={WIDTH}x{HEIGHT}:"
        f"fps=30,"
        f"format=yuv420p"
    )

    run_command(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            image_path,
            "-vf",
            filter_complex,
            "-t",
            f"{duration:.2f}",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            output_path
        ]
    )


# ============================================================
# Concatenate scenes
# ============================================================

def concatenate_scenes(
    scene_files,
    output_path
):

    concat_file = os.path.join(
        SCENE_DIR,
        "concat.txt"
    )

    with open(
        concat_file,
        "w",
        encoding="utf-8"
    ) as f:

        for scene_file in scene_files:

            absolute_path = os.path.abspath(
                scene_file
            )

            escaped = absolute_path.replace(
                "'",
                "'\\''"
            )

            f.write(
                f"file '{escaped}'\n"
            )

    run_command(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file,
            "-c",
            "copy",
            output_path
        ]
    )


# ============================================================
# Add narration
# ============================================================

def add_narration(
    video_path,
    audio_path,
    output_path
):

    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-i",
            audio_path,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            output_path
        ]
    )


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 60)
    print(
        "STEP 10B - VIDEO RENDERING"
    )
    print(
        "TARGET: 3:15 - 3:45"
    )
    print("=" * 60)

    package = load_content()

    scenes = get_scenes(
        package
    )

    # --------------------------------------------------------
    # Create one combined narration
    # --------------------------------------------------------

    narration_parts = []

    for scene in scenes:

        text = str(
            scene.get(
                "narration",
                ""
            )
        ).strip()

        if text:
            narration_parts.append(
                text
            )

    full_narration = " ".join(
        narration_parts
    ).strip()

    if not full_narration:

        raise RuntimeError(
            "No narration available."
        )

    full_audio = os.path.join(
        AUDIO_DIR,
        "full_narration.mp3"
    )

    print(
        "Generating complete voice..."
    )

    create_voice(
        full_narration,
        full_audio
    )

    audio_duration = get_duration(
        full_audio
    )

    print(
        f"Voice duration: "
        f"{audio_duration:.2f} seconds"
    )

    # --------------------------------------------------------
    # Hard safety check
    # --------------------------------------------------------

    if audio_duration < TARGET_MIN_SECONDS:

        print(
            "Voice is shorter than target."
        )

        print(
            "Using available narration."
        )

    if audio_duration > TARGET_MAX_SECONDS:

        print(
            "Voice is longer than 3:45."
        )

        print(
            "Video will be trimmed to 3:45."
        )

        target_duration = (
            TARGET_MAX_SECONDS
        )

    else:

        target_duration = audio_duration

    # --------------------------------------------------------
    # Divide duration between scenes
    # --------------------------------------------------------

    scene_count = len(
        scenes
    )

    scene_duration = (
        target_duration /
        scene_count
    )

    print(
        f"Scene duration: "
        f"{scene_duration:.2f} seconds"
    )

    scene_files = []

    # --------------------------------------------------------
    # Render each scene
    # --------------------------------------------------------

    for index, scene in enumerate(
        scenes,
        start=1
    ):

        print()
        print(
            "=" * 50
        )

        print(
            f"Rendering scene "
            f"{index}/{scene_count}"
        )

        query = str(
            scene.get(
                "visual_query",
                package.get(
                    "topic",
                    "AI technology"
                )
            )
        ).strip()

        if not query:

            query = (
                "artificial intelligence "
                "technology"
            )

        raw_image = os.path.join(
            IMAGE_DIR,
            f"scene_{index}_raw.jpg"
        )

        final_image = os.path.join(
            IMAGE_DIR,
            f"scene_{index}.jpg"
        )

        scene_video = os.path.join(
            SCENE_DIR,
            f"scene_{index}.mp4"
        )

        print(
            "Visual query:",
            query
        )

        download_image(
            query,
            raw_image,
            index
        )

        prepare_image(
            raw_image,
            final_image
        )

        create_scene_video(
            final_image,
            scene_video,
            scene_duration,
            index
        )

        scene_files.append(
            scene_video
        )

    # --------------------------------------------------------
    # Concatenate visual scenes
    # --------------------------------------------------------

    silent_video = os.path.join(
        VIDEO_DIR,
        "silent_long_video.mp4"
    )

    print()
    print(
        "Combining scenes..."
    )

    concatenate_scenes(
        scene_files,
        silent_video
    )

    # --------------------------------------------------------
    # Add narration
    # --------------------------------------------------------

    print(
        "Adding narration..."
    )

    add_narration(
        silent_video,
        full_audio,
        OUTPUT_VIDEO
    )

    # --------------------------------------------------------
    # Final duration
    # --------------------------------------------------------

    final_duration = get_duration(
        OUTPUT_VIDEO
    )

    # Force final video not to exceed 3:45
    if final_duration > TARGET_MAX_SECONDS:

        print(
            "Final video exceeds 3:45."
        )

        trimmed_video = os.path.join(
            VIDEO_DIR,
            "trimmed_final.mp4"
        )

        run_command(
            [
                "ffmpeg",
                "-y",
                "-i",
                OUTPUT_VIDEO,
                "-t",
                str(TARGET_MAX_SECONDS),
                "-c",
                "copy",
                trimmed_video
            ]
        )

        os.replace(
            trimmed_video,
            OUTPUT_VIDEO
        )

        final_duration = get_duration(
            OUTPUT_VIDEO
        )

    print()
    print("=" * 60)
    print(
        "VIDEO RENDERING COMPLETE"
    )
    print(
        f"Final duration: "
        f"{final_duration:.2f} seconds"
    )
    print(
        f"Output: {OUTPUT_VIDEO}"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
