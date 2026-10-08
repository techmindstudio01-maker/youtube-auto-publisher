import os
import json
import math
import subprocess
import requests
import asyncio
import edge_tts

from PIL import Image, ImageDraw, ImageFont


# ============================================================
# TechMind Studio - Video Renderer
# STEP 10B
# ============================================================

CONTENT_FILE = "content_package.json"

VIDEO_DIR = "video_assets"
IMAGE_DIR = os.path.join(VIDEO_DIR, "images")
AUDIO_DIR = os.path.join(VIDEO_DIR, "audio")
SCENE_DIR = os.path.join(VIDEO_DIR, "scenes")

OUTPUT_VIDEO = "techmind_studio_long.mp4"


# ============================================================
# DIRECTORIES
# ============================================================

for folder in [
    VIDEO_DIR,
    IMAGE_DIR,
    AUDIO_DIR,
    SCENE_DIR
]:
    os.makedirs(folder, exist_ok=True)


# ============================================================
# HELPERS
# ============================================================

def run_command(command):

    print()
    print("Running:")
    print(" ".join(command))

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    if result.returncode != 0:

        print(result.stdout)

        raise RuntimeError(
            "Command failed."
        )

    return result.stdout


def safe_name(text):

    text = str(text)

    result = ""

    for char in text:

        if (
            char.isalnum()
            or char in "-_"
        ):
            result += char
        else:
            result += "_"

    return result[:80]


# ============================================================
# LOAD CONTENT
# ============================================================

def load_content():

    if not os.path.exists(
        CONTENT_FILE
    ):
        raise RuntimeError(
            "content_package.json not found."
        )

    with open(
        CONTENT_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    if not data.get("scenes"):

        raise RuntimeError(
            "No scenes found in content_package.json."
        )

    print()
    print("=" * 60)
    print("CONTENT LOADED")
    print("=" * 60)

    print(
        "Title:",
        data.get("title")
    )

    print(
        "Script words:",
        data.get("script_word_count")
    )

    print(
        "Scenes:",
        len(data.get("scenes", []))
    )

    return data


# ============================================================
# WIKIMEDIA IMAGE SEARCH
# ============================================================

def search_wikimedia(
    query
):

    print()
    print(
        "Searching visual:",
        query
    )

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
        "iiurlwidth": 1280,
        "format": "json"
    }

    headers = {
        "User-Agent":
            "TechMindStudio/1.0 "
            "(automated educational video creator)"
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

        pages = (
            data
            .get("query", {})
            .get("pages", {})
        )

        candidates = []

        for page in pages.values():

            imageinfo = page.get(
                "imageinfo",
                []
            )

            if not imageinfo:
                continue

            info = imageinfo[0]

            image_url = (
                info.get("thumburl")
                or info.get("url")
            )

            if image_url:
                candidates.append(
                    image_url
                )

        if candidates:

            # Try random result so videos
            # don't always use the first image.
            return candidates[
                min(
                    len(candidates) - 1,
                    0
                )
            ]

    except Exception as e:

        print(
            "Wikimedia search failed:",
            e
        )

    return None


# ============================================================
# DOWNLOAD IMAGE
# ============================================================

def download_image(
    url,
    output_file
):

    headers = {
        "User-Agent":
            "TechMindStudio/1.0"
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=45
    )

    response.raise_for_status()

    with open(
        output_file,
        "wb"
    ) as f:

        f.write(
            response.content
        )

    return output_file


# ============================================================
# FALLBACK VISUAL
# ============================================================

def create_fallback_image(
    text,
    output_file
):

    width = 1280
    height = 720

    image = Image.new(
        "RGB",
        (width, height),
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

    words = str(text).split()

    lines = []
    current = ""

    for word in words:

        test = (
            current + " " + word
        ).strip()

        if len(test) > 30:

            lines.append(
                current
            )

            current = word

        else:

            current = test

    if current:
        lines.append(current)

    y = height // 2 - (
        len(lines) * 35
    )

    for line in lines:

        bbox = draw.textbbox(
            (0, 0),
            line,
            font=font
        )

        text_width = (
            bbox[2] - bbox[0]
        )

        x = (
            width - text_width
        ) // 2

        draw.text(
            (x, y),
            line,
            font=font,
            fill="white"
        )

        y += 75

    image.save(
        output_file,
        quality=95
    )


# ============================================================
# PREPARE IMAGE
# ============================================================

def prepare_image(
    input_file,
    output_file
):

    try:

        image = Image.open(
            input_file
        ).convert("RGB")

        target_ratio = 16 / 9

        width, height = (
            image.size
        )

        current_ratio = (
            width / height
        )

        if current_ratio > target_ratio:

            new_width = int(
                height * target_ratio
            )

            left = (
                width - new_width
            ) // 2

            image = image.crop(
                (
                    left,
                    0,
                    left + new_width,
                    height
                )
            )

        else:

            new_height = int(
                width / target_ratio
            )

            top = (
                height - new_height
            ) // 2

            image = image.crop(
                (
                    0,
                    top,
                    width,
                    top + new_height
                )
            )

        image = image.resize(
            (1280, 720),
            Image.Resampling.LANCZOS
        )

        image.save(
            output_file,
            "JPEG",
            quality=94
        )

        return output_file

    except Exception as e:

        print(
            "Image processing failed:",
            e
        )

        create_fallback_image(
            "TechMind Studio",
            output_file
        )

        return output_file


# ============================================================
# DOWNLOAD ALL SCENE VISUALS
# ============================================================

def prepare_scene_images(
    scenes
):

    image_files = []

    for index, scene in enumerate(
        scenes,
        start=1
    ):

        query = scene.get(
            "visual_query",
            "artificial intelligence technology"
        )

        raw_file = os.path.join(
            IMAGE_DIR,
            f"raw_{index}.jpg"
        )

        final_file = os.path.join(
            IMAGE_DIR,
            f"scene_{index}.jpg"
        )

        try:

            image_url = search_wikimedia(
                query
            )

            if image_url:

                print(
                    "Downloading visual..."
                )

                download_image(
                    image_url,
                    raw_file
                )

                prepare_image(
                    raw_file,
                    final_file
                )

            else:

                print(
                    "No image found. "
                    "Creating fallback visual."
                )

                create_fallback_image(
                    scene.get(
                        "heading",
                        "AI Technology"
                    ),
                    final_file
                )

        except Exception as e:

            print(
                "Visual failed:",
                e
            )

            create_fallback_image(
                scene.get(
                    "heading",
                    "AI Technology"
                ),
                final_file
            )

        image_files.append(
            final_file
        )

    return image_files


# ============================================================
# TEXT TO SPEECH
# ============================================================

async def generate_voice(
    text,
    output_file
):

    communicate = edge_tts.Communicate(
        text,
        voice="en-US-AriaNeural",
        rate="-5%",
        volume="+0%"
    )

    await communicate.save(
        output_file
    )


def create_voice(
    text,
    output_file
):

    print()
    print(
        "Generating AI voice..."
    )

    asyncio.run(
        generate_voice(
            text,
            output_file
        )
    )

    if not os.path.exists(
        output_file
    ):
        raise RuntimeError(
            "Voice generation failed."
        )


# ============================================================
# GET AUDIO DURATION
# ============================================================

def get_duration(
    filename
):

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        filename
    ]

    output = run_command(
        command
    )

    return float(
        output.strip()
    )


# ============================================================
# CREATE SCENE VIDEO
# ============================================================

def create_scene_video(
    image_file,
    output_file,
    duration,
    scene_number
):

    # Alternate motion direction.
    if scene_number % 2 == 0:

        zoom_filter = (
            "scale=1280:720,"
            "zoompan="
            "z='min(zoom+0.0008,1.12)':"
            "x='iw/2-(iw/zoom/2)':"
            "y='ih/2-(ih/zoom/2)':"
            "d=1"
            ":s=1280x720"
        )

    else:

        zoom_filter = (
            "scale=1280:720,"
            "zoompan="
            "z='min(zoom+0.0008,1.12)':"
            "x='iw/2-(iw/zoom/2)':"
            "y='ih/2-(ih/zoom/2)':"
            "d=1"
            ":s=1280x720"
        )

    fps = 30

    frames = max(
        1,
        int(
            duration * fps
        )
    )

    filter_complex = (
        "scale=1280:720,"
        "zoompan="
        f"z='min(zoom+0.0005,1.10)':"
        "x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':"
        f"d={frames}"
        ":s=1280x720:"
        "fps=30"
    )

    command = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        image_file,
        "-vf",
        filter_complex,
        "-t",
        str(duration),
        "-r",
        "30",
        "-pix_fmt",
        "yuv420p",
        "-an",
        output_file
    ]

    run_command(
        command
    )


# ============================================================
# CONCATENATE SCENES
# ============================================================

def concatenate_scenes(
    scene_files,
    output_file
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

            absolute = os.path.abspath(
                scene_file
            )

            f.write(
                "file '"
                + absolute.replace(
                    "'",
                    "'\\''"
                )
                + "'\n"
            )

    command = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_file,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        output_file
    ]

    run_command(
        command
    )


# ============================================================
# ADD VOICEOVER
# ============================================================

def add_voiceover(
    video_file,
    audio_file,
    output_file
):

    command = [
        "ffmpeg",
        "-y",
        "-i",
        video_file,
        "-i",
        audio_file,
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
        "-movflags",
        "+faststart",
        output_file
    ]

    run_command(
        command
    )


# ============================================================
# MAIN RENDER
# ============================================================

def main():

    print()
    print("=" * 60)
    print("STEP 10B - VIDEO RENDERING")
    print("=" * 60)

    package = load_content()

    scenes = package.get(
        "scenes",
        []
    )

    # ----------------------------------------
    # Full script
    # ----------------------------------------

    script = package.get(
        "script",
        ""
    ).strip()

    if not script:

        # Safety fallback:
        # combine scene narration.
        script = " ".join(
            scene.get(
                "narration",
                ""
            ).strip()
            for scene in scenes
        )

    if not script:

        raise RuntimeError(
            "No narration available."
        )

    # ----------------------------------------
    # Images
    # ----------------------------------------

    print()
    print(
        "Preparing scene visuals..."
    )

    image_files = prepare_scene_images(
        scenes
    )

    # ----------------------------------------
    # Voice
    # ----------------------------------------

    audio_file = os.path.join(
        AUDIO_DIR,
        "narration.mp3"
    )

    create_voice(
        script,
        audio_file
    )

    audio_duration = get_duration(
        audio_file
    )

    print(
        f"Voice duration: "
        f"{audio_duration:.1f} seconds"
    )

    # ----------------------------------------
    # Scene duration
    # ----------------------------------------

    scene_duration = (
        audio_duration
        / len(image_files)
    )

    print(
        f"Average scene duration: "
        f"{scene_duration:.1f} seconds"
    )

    # ----------------------------------------
    # Render scenes
    # ----------------------------------------

    scene_files = []

    for index, image_file in enumerate(
        image_files,
        start=1
    ):

        scene_output = os.path.join(
            SCENE_DIR,
            f"scene_{index}.mp4"
        )

        print()
        print(
            f"Rendering scene "
            f"{index}/{len(image_files)}"
        )

        create_scene_video(
            image_file=image_file,
            output_file=scene_output,
            duration=scene_duration,
            scene_number=index
        )

        scene_files.append(
            scene_output
        )

    # ----------------------------------------
    # Join scenes
    # ----------------------------------------

    silent_video = os.path.join(
        VIDEO_DIR,
        "silent_video.mp4"
    )

    concatenate_scenes(
        scene_files,
        silent_video
    )

    # ----------------------------------------
    # Add narration
    # ----------------------------------------

    add_voiceover(
        silent_video,
        audio_file,
        OUTPUT_VIDEO
    )

    # ----------------------------------------
    # Final check
    # ----------------------------------------

    final_duration = get_duration(
        OUTPUT_VIDEO
    )

    print()
    print("=" * 60)
    print("VIDEO RENDER COMPLETE")
    print("=" * 60)

    print(
        "Output:",
        OUTPUT_VIDEO
    )

    print(
        f"Duration: "
        f"{final_duration:.1f} seconds"
    )

    print(
        f"Duration: "
        f"{final_duration / 60:.2f} minutes"
    )

    print(
        "Scenes:",
        len(scene_files)
    )

    print("=" * 60)


if __name__ == "__main__":
    main()
