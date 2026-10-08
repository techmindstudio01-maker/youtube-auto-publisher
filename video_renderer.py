import os
import re
import json
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# ============================================================
# TECHMIND STUDIO
# ORIGINAL 4K MOTION GRAPHICS VIDEO RENDERER
# ============================================================

WIDTH = 3840
HEIGHT = 2160
FPS = 30

MAX_DURATION = 230
MIN_DURATION = 180

BRAND = "TECHMIND STUDIO"

PACKAGE_FILE = Path("content_package.json")
OUTPUT_FILE = Path("techmind_studio_long.mp4")

WORK_DIR = Path("render_work")
FRAMES_DIR = WORK_DIR / "frames"
SEGMENTS_DIR = WORK_DIR / "segments"

VOICE_FILE = WORK_DIR / "narration.mp3"

FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


# ============================================================
# COMMAND HELPER
# ============================================================

def run(cmd):
    print("\nRUNNING:")
    print(" ".join(str(x) for x in cmd))

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    print(result.stdout)

    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed with code {result.returncode}"
        )


def probe_duration(path):
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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        return float(result.stdout.strip())
    except Exception:
        return 0


# ============================================================
# CLEAN WORKSPACE
# ============================================================

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)

FRAMES_DIR.mkdir(parents=True, exist_ok=True)
SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# LOAD CONTENT PACKAGE
# ============================================================

if not PACKAGE_FILE.exists():
    raise RuntimeError(
        "content_package.json not found."
    )

with open(
    PACKAGE_FILE,
    "r",
    encoding="utf-8"
) as f:
    package = json.load(f)


title = str(
    package.get(
        "title",
        "I Built a Viral YouTube Channel Using AI"
    )
)

script = str(
    package.get(
        "script",
        ""
    )
)

scenes = package.get(
    "scenes",
    []
)

if not script:
    raise RuntimeError(
        "No script found in content_package.json."
    )


# ============================================================
# TEXT HELPERS
# ============================================================

def clean(text):
    if not text:
        return ""

    text = str(text)

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def words(text):
    return clean(text).split()


def shorten(text, count=10):
    parts = words(text)

    if len(parts) <= count:
        return " ".join(parts)

    return " ".join(parts[:count]) + "..."


def safe_filename(text):
    return re.sub(
        r"[^a-zA-Z0-9_-]",
        "_",
        text
    )


# ============================================================
# FONT
# ============================================================

def font(size, bold=False):

    path = (
        FONT_BOLD
        if bold
        else FONT_REGULAR
    )

    if os.path.exists(path):
        return ImageFont.truetype(
            path,
            size
        )

    return ImageFont.load_default()


FONT_SMALL = font(52)
FONT_BODY = font(68)
FONT_MEDIUM = font(88)
FONT_BIG = font(130, True)
FONT_HUGE = font(190, True)
FONT_TITLE = font(230, True)


# ============================================================
# DRAW HELPERS
# ============================================================

def rounded_box(
    draw,
    xy,
    radius,
    fill,
    outline=None,
    width=1
):
    draw.rounded_rectangle(
        xy,
        radius=radius,
        fill=fill,
        outline=outline,
        width=width
    )


def center_text(
    draw,
    text,
    y,
    fnt,
    fill=(245, 247, 255)
):
    box = draw.textbbox(
        (0, 0),
        text,
        font=fnt
    )

    tw = box[2] - box[0]

    draw.text(
        (
            (WIDTH - tw) // 2,
            y
        ),
        text,
        font=fnt,
        fill=fill
    )


def draw_brand(draw):

    draw.text(
        (
            110,
            HEIGHT - 115
        ),
        BRAND,
        font=FONT_SMALL,
        fill=(145, 155, 175)
    )


def draw_grid(draw):

    for x in range(
        0,
        WIDTH,
        160
    ):
        draw.line(
            [
                (x, 0),
                (x, HEIGHT)
            ],
            fill=(28, 34, 48),
            width=2
        )

    for y in range(
        0,
        HEIGHT,
        160
    ):
        draw.line(
            [
                (0, y),
                (WIDTH, y)
            ],
            fill=(28, 34, 48),
            width=2
        )


def draw_top_bar(
    draw,
    section="AI CREATOR WORKFLOW"
):

    rounded_box(
        draw,
        (
            80,
            70,
            WIDTH - 80,
            190
        ),
        45,
        (18, 24, 38)
    )

    draw.text(
        (
            130,
            108
        ),
        section.upper(),
        font=FONT_BODY,
        fill=(235, 240, 250)
    )

    draw.text(
        (
            WIDTH - 520,
            120
        ),
        "●  LIVE",
        font=FONT_SMALL,
        fill=(120, 220, 165)
    )


# ============================================================
# BASE BACKGROUND
# ============================================================

def base_canvas():

    img = Image.new(
        "RGB",
        (
            WIDTH,
            HEIGHT
        ),
        (8, 12, 22)
    )

    draw = ImageDraw.Draw(img)

    draw_grid(draw)

    return img


# ============================================================
# HOOK FRAME
# ============================================================

def make_hook_frame():

    img = base_canvas()

    draw = ImageDraw.Draw(img)

    center_text(
        draw,
        "WHAT IF AI",
        470,
        FONT_BIG
    )

    center_text(
        draw,
        "BUILT YOUR",
        650,
        FONT_BIG
    )

    center_text(
        draw,
        "YOUTUBE CHANNEL?",
        830,
        FONT_TITLE
    )

    rounded_box(
        draw,
        (
            1240,
            1190,
            2600,
            1380
        ),
        60,
        (30, 90, 180)
    )

    center_text(
        draw,
        "NICHE → SCRIPT → VIDEO → UPLOAD",
        1240,
        FONT_BODY
    )

    draw_brand(draw)

    return img


# ============================================================
# SEARCH / NICHE FRAME
# ============================================================

def make_niche_frame(scene_text):

    img = base_canvas()

    draw = ImageDraw.Draw(img)

    draw_top_bar(
        draw,
        "STEP 1 — FIND THE NICHE"
    )

    draw.text(
        (150, 340),
        "YouTube Search",
        font=FONT_BIG,
        fill=(245, 248, 255)
    )

    rounded_box(
        draw,
        (
            150,
            560,
            3690,
            780
        ),
        55,
        (25, 32, 48),
        outline=(75, 90, 120),
        width=4
    )

    query = (
        "best AI tools for creators"
    )

    draw.text(
        (
            230,
            615
        ),
        query,
        font=FONT_BODY,
        fill=(225, 230, 240)
    )

    draw.text(
        (
            3350,
            610
        ),
        "⌕",
        font=FONT_BIG,
        fill=(120, 170, 255)
    )

    labels = [
        ("SEARCH DEMAND", 86),
        ("COMPETITION", 61),
        ("AUDIENCE INTEREST", 92),
    ]

    y = 950

    for label, value in labels:

        draw.text(
            (
                180,
                y
            ),
            label,
            font=FONT_BODY,
            fill=(200, 208, 220)
        )

        rounded_box(
            draw,
            (
                1250,
                y + 20,
                3200,
                y + 90
            ),
            30,
            (35, 43, 60)
        )

        bar_width = int(
            1950 * value / 100
        )

        rounded_box(
            draw,
            (
                1250,
                y + 20,
                1250 + bar_width,
                y + 90
            ),
            30,
            (70, 150, 255)
        )

        draw.text(
            (
                3300,
                y - 5
            ),
            f"{value}%",
            font=FONT_BODY,
            fill=(245, 248, 255)
        )

        y += 230

    draw_brand(draw)

    return img


# ============================================================
# FLOW FRAME
# ============================================================

def make_flow_frame(
    title_text,
    step_text
):

    img = base_canvas()

    draw = ImageDraw.Draw(img)

    draw_top_bar(
        draw,
        title_text
    )

    steps = [
        "NICHE",
        "TOPIC",
        "HOOK",
        "SCRIPT",
        "VIDEO",
        "UPLOAD"
    ]

    start_x = 180
    box_w = 500
    gap = 100

    y = 800

    for i, step in enumerate(steps):

        x = start_x + i * (
            box_w + gap
        )

        if x + box_w > WIDTH:
            break

        fill = (
            (40, 115, 220)
            if i == 0
            else (24, 32, 48)
        )

        rounded_box(
            draw,
            (
                x,
                y,
                x + box_w,
                y + 250
            ),
            45,
            fill,
            outline=(75, 95, 125),
            width=4
        )

        center_x = x + box_w // 2

        box = draw.textbbox(
            (0, 0),
            step,
            font=FONT_BODY
        )

        tw = box[2] - box[0]

        draw.text(
            (
                center_x - tw // 2,
                y + 78
            ),
            step,
            font=FONT_BODY,
            fill=(245, 248, 255)
        )

        if i < len(steps) - 1:

            arrow_x = (
                x
                + box_w
                + 20
            )

            draw.text(
                (
                    arrow_x,
                    y + 75
                ),
                "→",
                font=FONT_BIG,
                fill=(100, 160, 255)
            )

    rounded_box(
        draw,
        (
            600,
            1260,
            3240,
            1560
        ),
        55,
        (17, 26, 42)
    )

    center_text(
        draw,
        shorten(step_text, 12),
        1350,
        FONT_BODY
    )

    draw_brand(draw)

    return img


# ============================================================
# AI TOOL FRAME
# ============================================================

def make_tools_frame():

    img = base_canvas()

    draw = ImageDraw.Draw(img)

    draw_top_bar(
        draw,
        "AI TOOL STACK"
    )

    tools = [
        (
            "RESEARCH",
            "Find demand"
        ),
        (
            "SCRIPT",
            "Build the story"
        ),
        (
            "VOICE",
            "Natural narration"
        ),
        (
            "VISUALS",
            "Create scenes"
        ),
        (
            "EDIT",
            "Assemble video"
        ),
        (
            "THUMBNAIL",
            "Increase CTR"
        )
    ]

    cols = 3

    card_w = 1050
    card_h = 520

    start_x = 180
    start_y = 390

    for i, (name, desc) in enumerate(tools):

        row = i // cols
        col = i % cols

        x = (
            start_x
            + col * 1180
        )

        y = (
            start_y
            + row * 650
        )

        rounded_box(
            draw,
            (
                x,
                y,
                x + card_w,
                y + card_h
            ),
            55,
            (19, 27, 42),
            outline=(55, 75, 105),
            width=4
        )

        draw.text(
            (
                x + 65,
                y + 70
            ),
            name,
            font=FONT_MEDIUM,
            fill=(245, 248, 255)
        )

        draw.text(
            (
                x + 65,
                y + 210
            ),
            desc,
            font=FONT_BODY,
            fill=(160, 175, 200)
        )

        rounded_box(
            draw,
            (
                x + 65,
                y + 355,
                x + 300,
                y + 425
            ),
            25,
            (35, 95, 180)
        )

        draw.text(
            (
                x + 105,
                y + 365
            ),
            "AI POWERED",
            font=font(40, True),
            fill=(240, 245, 255)
        )

    draw_brand(draw)

    return img


# ============================================================
# GRAPH FRAME
# ============================================================

def make_growth_frame():

    img = base_canvas()

    draw = ImageDraw.Draw(img)

    draw_top_bar(
        draw,
        "VIRAL POTENTIAL"
    )

    chart_left = 280
    chart_top = 500
    chart_right = 3500
    chart_bottom = 1650

    draw.line(
        [
            (chart_left, chart_bottom),
            (chart_right, chart_bottom)
        ],
        fill=(95, 110, 135),
        width=5
    )

    draw.line(
        [
            (chart_left, chart_top),
            (chart_left, chart_bottom)
        ],
        fill=(95, 110, 135),
        width=5
    )

    points = [
        (350, 1530),
        (800, 1450),
        (1250, 1360),
        (1700, 1200),
        (2150, 1010),
        (2600, 760),
        (3050, 530),
        (3450, 400)
    ]

    for i in range(
        len(points) - 1
    ):

        draw.line(
            [
                points[i],
                points[i + 1]
            ],
            fill=(75, 155, 255),
            width=18
        )

    for x, y in points:

        draw.ellipse(
            (
                x - 24,
                y - 24,
                x + 24,
                y + 24
            ),
            fill=(100, 180, 255)
        )

    draw.text(
        (
            300,
            330
        ),
        "DEMAND",
        font=FONT_BIG,
        fill=(245, 248, 255)
    )

    draw.text(
        (
            280,
            1740
        ),
        "TIME →",
        font=FONT_BODY,
        fill=(150, 165, 185)
    )

    draw_brand(draw)

    return img


# ============================================================
# CTA FRAME
# ============================================================

def make_cta_frame():

    img = base_canvas()

    draw = ImageDraw.Draw(img)

    center_text(
        draw,
        "ENJOYED THE VIDEO?",
        400,
        FONT_BIG
    )

    # LIKE
    rounded_box(
        draw,
        (
            480,
            850,
            1350,
            1110
        ),
        65,
        (28, 42, 65)
    )

    draw.text(
        (
            650,
            900
        ),
        "👍",
        font=FONT_BIG,
        fill=(245, 248, 255)
    )

    draw.text(
        (
            850,
            935
        ),
        "LIKE",
        font=FONT_BODY,
        fill=(245, 248, 255)
    )

    # SHARE
    rounded_box(
        draw,
        (
            1480,
            850,
            2360,
            1110
        ),
        65,
        (28, 42, 65)
    )

    draw.text(
        (
            1640,
            900
        ),
        "↗",
        font=FONT_BIG,
        fill=(100, 180, 255)
    )

    draw.text(
        (
            1860,
            935
        ),
        "SHARE",
        font=FONT_BODY,
        fill=(245, 248, 255)
    )

    # SUBSCRIBE
    rounded_box(
        draw,
        (
            2490,
            850,
            3360,
            1110
        ),
        65,
        (210, 40, 55)
    )

    draw.text(
        (
            2600,
            905
        ),
        "▶",
        font=FONT_BIG,
        fill=(255, 255, 255)
    )

    draw.text(
        (
            2810,
            935
        ),
        "SUBSCRIBE",
        font=font(65, True),
        fill=(255, 255, 255)
    )

    center_text(
        draw,
        "TECHMIND STUDIO",
        1350,
        FONT_MEDIUM,
        (160, 175, 200)
    )

    return img


# ============================================================
# GENERIC SCENE FRAME
# ============================================================

def make_scene_frame(
    scene_number,
    scene
):

    narration = clean(
        scene.get(
            "narration",
            ""
        )
    )

    visual_query = clean(
        scene.get(
            "visual_query",
            ""
        )
    )

    screen_text = clean(
        scene.get(
            "on_screen_text",
            ""
        )
    )

    visual_type = clean(
        scene.get(
            "visual_type",
            "motion graphic"
        )
    )

    # Decide visual based on scene number
    mode = scene_number % 5

    if mode == 0:
        return make_niche_frame(
            narration
        )

    if mode == 1:
        return make_flow_frame(
            visual_type
            or "AI WORKFLOW",
            screen_text
            or narration
        )

    if mode == 2:
        return make_tools_frame()

    if mode == 3:
        return make_growth_frame()

    return make_flow_frame(
        "STEP BY STEP",
        screen_text
        or shorten(
            narration,
            14
        )
    )


# ============================================================
# CREATE VISUAL FRAMES
# ============================================================

print(
    "\n=========================================="
)

print(
    "TECHMIND STUDIO 4K RENDERER"
)

print(
    "Creating original motion graphics..."
)

print(
    "=========================================="
)


# Intro
hook_path = FRAMES_DIR / "000_hook.png"

make_hook_frame().save(
    hook_path
)


# Scene frames
scene_frames = []

for index, scene in enumerate(
    scenes
):

    path = (
        FRAMES_DIR
        / f"scene_{index + 1:03d}.png"
    )

    print(
        "Creating scene frame:",
        index + 1
    )

    frame = make_scene_frame(
        index,
        scene
    )

    frame.save(
        path
    )

    scene_frames.append(
        path
    )


# CTA
cta_path = FRAMES_DIR / "999_cta.png"

make_cta_frame().save(
    cta_path
)


# ============================================================
# NARRATION
# ============================================================

print(
    "\n=========================================="
)

print(
    "Generating narration..."
)

print(
    "=========================================="
)

voice = "en-US-AriaNeural"

run([
    "edge-tts",
    "--voice",
    voice,
    "--rate",
    "-5%",
    "--text",
    script,
    "--write-media",
    str(VOICE_FILE)
])


audio_duration = probe_duration(
    VOICE_FILE
)

if audio_duration <= 0:
    raise RuntimeError(
        "Could not determine narration duration."
    )

print(
    "Narration:",
    round(audio_duration, 2),
    "seconds"
)


# ============================================================
# TIMELINE
# ============================================================

target_duration = min(
    audio_duration,
    MAX_DURATION
)

# Keep the visuals moving frequently.
#
# Intro: 8 sec
# Scenes: roughly 8–12 sec
# CTA: 6 sec

timeline = []

intro_duration = min(
    8,
    target_duration
)

timeline.append(
    (
        hook_path,
        intro_duration
    )
)

remaining = (
    target_duration
    - intro_duration
)

if not scene_frames:
    raise RuntimeError(
        "No scenes found in content_package.json."
    )


# Estimate scene duration from narration words
scene_durations = []

for scene in scenes:

    narration = clean(
        scene.get(
            "narration",
            ""
        )
    )

    count = len(
        words(narration)
    )

    estimated = max(
        7,
        count / 2.45
    )

    scene_durations.append(
        estimated
    )


total_estimated = sum(
    scene_durations
)

scale = (
    remaining
    / total_estimated
    if total_estimated > 0
    else 1
)


for index, frame_path in enumerate(
    scene_frames
):

    duration = (
        scene_durations[index]
        * scale
    )

    # Keep visual segments in the
    # requested 6–12 second range.
    duration = max(
        6,
        min(
            12,
            duration
        )
    )

    if remaining <= 0:
        break

    duration = min(
        duration,
        remaining
    )

    timeline.append(
        (
            frame_path,
            duration
        )
    )

    remaining -= duration


# Fill remaining time
last_index = 0

while remaining > 0.2:

    frame_path = scene_frames[
        last_index % len(scene_frames)
    ]

    duration = min(
        10,
        remaining
    )

    timeline.append(
        (
            frame_path,
            duration
        )
    )

    remaining -= duration

    last_index += 1


print(
    "\nVisual segments:",
    len(timeline)
)


# ============================================================
# FFmpeg MOTION FILTER
# ============================================================

def render_segment(
    image_path,
    output_path,
    duration,
    index
):

    frames = max(
        1,
        int(
            duration * FPS
        )
    )

    # Very subtle movement.
    # No aggressive shaking.
    if index % 2 == 0:

        zoom_start = 1.00
        zoom_end = 1.012

    else:

        zoom_start = 1.012
        zoom_end = 1.00

    step = (
        zoom_end
        - zoom_start
    ) / frames

    vf = (
        f"scale={WIDTH}:{HEIGHT}:"
        f"force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},"
        f"zoompan="
        f"z='"
        f"{zoom_start}+"
        f"{step}*on':"
        f"d=1:"
        f"s={WIDTH}x{HEIGHT}:"
        f"fps={FPS},"
        f"format=yuv420p"
    )

    run([
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-t",
        str(duration),
        "-vf",
        vf,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        str(output_path)
    ])


# ============================================================
# RENDER SEGMENTS
# ============================================================

segment_files = []

for index, (
    image_path,
    duration
) in enumerate(timeline):

    output = (
        SEGMENTS_DIR
        / f"segment_{index:03d}.mp4"
    )

    print(
        f"\nRendering "
        f"{index + 1}/{len(timeline)} "
        f"({duration:.1f}s)"
    )

    render_segment(
        image_path,
        output,
        duration,
        index
    )

    segment_files.append(
        output
    )


# ============================================================
# CONCAT
# ============================================================

concat_file = (
    WORK_DIR
    / "concat.txt"
)

with open(
    concat_file,
    "w",
    encoding="utf-8"
) as f:

    for file in segment_files:

        absolute = str(
            file.resolve()
        )

        absolute = absolute.replace(
            "'",
            "'\\''"
        )

        f.write(
            f"file '{absolute}'\n"
        )


visual_video = (
    WORK_DIR
    / "visual_video.mp4"
)

run([
    "ffmpeg",
    "-y",
    "-f",
    "concat",
    "-safe",
    "0",
    "-i",
    str(concat_file),
    "-an",
    "-c",
    "copy",
    str(visual_video)
])


# ============================================================
# ADD AUDIO
# ============================================================

print(
    "\n=========================================="
)

print(
    "Combining 4K video + narration..."
)

print(
    "=========================================="
)

final_duration = min(
    target_duration,
    MAX_DURATION
)

run([
    "ffmpeg",
    "-y",
    "-i",
    str(visual_video),
    "-i",
    str(VOICE_FILE),
    "-map",
    "0:v:0",
    "-map",
    "1:a:0",
    "-t",
    str(final_duration),
    "-c:v",
    "copy",
    "-c:a",
    "aac",
    "-b:a",
    "192k",
    "-movflags",
    "+faststart",
    str(OUTPUT_FILE)
])


# ============================================================
# VALIDATION
# ============================================================

if not OUTPUT_FILE.exists():
    raise RuntimeError(
        "Final video was not created."
    )

duration = probe_duration(
    OUTPUT_FILE
)

print(
    "\n=========================================="
)

print(
    "FINAL RESULT"
)

print(
    "=========================================="
)

print(
    "Title:",
    title
)

print(
    "Resolution:",
    "3840x2160 (4K)"
)

print(
    "Duration:",
    round(duration, 2),
    "seconds"
)

print(
    "Visual segments:",
    len(timeline)
)

print(
    "Maximum visual duration:",
    max(
        duration
        for _, duration
        in timeline
    )
)

print(
    "Output:",
    OUTPUT_FILE
)

print(
    "=========================================="
)

print(
    "TECHMIND STUDIO 4K VIDEO READY"
)

print(
    "=========================================="
)
