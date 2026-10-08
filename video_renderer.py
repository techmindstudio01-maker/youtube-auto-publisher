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
# PREMIUM 4K TUTORIAL VIDEO RENDERER
# ============================================================

WIDTH = 3840
HEIGHT = 2160
FPS = 30

MAX_DURATION = 230
MIN_DURATION = 180

MAX_VISUAL_DURATION = 15.0
MIN_VISUAL_DURATION = 4.0

BRAND = "TECHMIND STUDIO"

PACKAGE_FILE = Path("content_package.json")
OUTPUT_FILE = Path("techmind_studio_long.mp4")

WORK_DIR = Path("render_work")
FRAMES_DIR = WORK_DIR / "frames"
SEGMENTS_DIR = WORK_DIR / "segments"

VOICE_FILE = WORK_DIR / "narration.mp3"
CONCAT_FILE = WORK_DIR / "concat.txt"
VISUAL_VIDEO = WORK_DIR / "visual_video.mp4"

FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


# ============================================================
# COMMAND RUNNER
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
        return float(
            result.stdout.strip()
        )
    except Exception:
        return 0.0


# ============================================================
# PREPARE WORKSPACE
# ============================================================

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)

FRAMES_DIR.mkdir(
    parents=True,
    exist_ok=True
)

SEGMENTS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


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
        "AI YouTube Automation"
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

if not script.strip():
    raise RuntimeError(
        "No script found in content_package.json."
    )

if not isinstance(
    scenes,
    list
) or not scenes:
    raise RuntimeError(
        "No scenes found in content_package.json."
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


def shorten(
    text,
    count=12
):
    parts = words(text)

    if len(parts) <= count:
        return " ".join(parts)

    return (
        " ".join(parts[:count])
        + "..."
    )


def wrap_text(
    draw,
    text,
    fnt,
    max_width
):

    text = clean(text)

    if not text:
        return []

    tokens = text.split()

    lines = []
    current = ""

    for token in tokens:

        test = (
            token
            if not current
            else current + " " + token
        )

        box = draw.textbbox(
            (0, 0),
            test,
            font=fnt
        )

        width = (
            box[2] - box[0]
        )

        if width <= max_width:
            current = test
        else:

            if current:
                lines.append(
                    current
                )

            current = token

    if current:
        lines.append(
            current
        )

    return lines


# ============================================================
# FONTS
# ============================================================

def font(
    size,
    bold=False
):

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


FONT_TINY = font(42)
FONT_SMALL = font(54)
FONT_BODY = font(70)
FONT_MEDIUM = font(92)
FONT_BIG = font(130, True)
FONT_HUGE = font(185, True)
FONT_TITLE = font(225, True)


# ============================================================
# DRAWING HELPERS
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
            100,
            HEIGHT - 110
        ),
        BRAND,
        font=FONT_SMALL,
        fill=(135, 150, 175)
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
            fill=(24, 31, 45),
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
            fill=(24, 31, 45),
            width=2
        )


def base_canvas():

    img = Image.new(
        "RGB",
        (
            WIDTH,
            HEIGHT
        ),
        (7, 11, 20)
    )

    draw = ImageDraw.Draw(img)

    draw_grid(draw)

    return img


def draw_top_bar(
    draw,
    section
):

    rounded_box(
        draw,
        (
            80,
            60,
            WIDTH - 80,
            195
        ),
        42,
        (17, 24, 38),
        outline=(43, 58, 82),
        width=3
    )

    draw.text(
        (
            130,
            100
        ),
        clean(section).upper(),
        font=FONT_BODY,
        fill=(235, 240, 250)
    )

    draw.ellipse(
        (
            WIDTH - 390,
            112,
            WIDTH - 355,
            147
        ),
        fill=(85, 220, 145)
    )

    draw.text(
        (
            WIDTH - 330,
            103
        ),
        "AI WORKFLOW",
        font=FONT_SMALL,
        fill=(155, 175, 195)
    )


def draw_progress(
    draw,
    progress
):

    progress = max(
        0,
        min(
            1,
            progress
        )
    )

    x1 = 100
    x2 = WIDTH - 100
    y = HEIGHT - 55

    draw.rounded_rectangle(
        (
            x1,
            y,
            x2,
            y + 12
        ),
        radius=6,
        fill=(35, 43, 58)
    )

    draw.rounded_rectangle(
        (
            x1,
            y,
            x1 + int(
                (x2 - x1)
                * progress
            ),
            y + 12
        ),
        radius=6,
        fill=(70, 150, 255)
    )


def draw_chip(
    draw,
    text,
    x,
    y,
    width=430
):

    rounded_box(
        draw,
        (
            x,
            y,
            x + width,
            y + 105
        ),
        30,
        (28, 48, 76),
        outline=(70, 120, 190),
        width=3
    )

    draw.text(
        (
            x + 35,
            y + 24
        ),
        text,
        font=FONT_SMALL,
        fill=(225, 235, 250)
    )


# ============================================================
# SCENE TYPE 1 — HOOK
# ============================================================

def make_hook_frame():

    img = base_canvas()
    draw = ImageDraw.Draw(img)

    draw.text(
        (
            220,
            380
        ),
        "WHAT IF",
        font=FONT_BIG,
        fill=(235, 240, 250)
    )

    draw.text(
        (
            220,
            560
        ),
        "AI BUILT",
        font=FONT_BIG,
        fill=(100, 175, 255)
    )

    draw.text(
        (
            220,
            760
        ),
        "YOUR YOUTUBE",
        font=FONT_HUGE,
        fill=(245, 248, 255)
    )

    draw.text(
        (
            220,
            1010
        ),
        "CHANNEL?",
        font=FONT_HUGE,
        fill=(245, 248, 255)
    )

    rounded_box(
        draw,
        (
            230,
            1380,
            3000,
            1605
        ),
        55,
        (20, 47, 82),
        outline=(65, 135, 220),
        width=4
    )

    draw.text(
        (
            330,
            1450
        ),
        "NICHE  →  SCRIPT  →  VIDEO  →  UPLOAD",
        font=FONT_BODY,
        fill=(225, 235, 250)
    )

    draw_brand(draw)

    return img


# ============================================================
# SCENE TYPE 2 — BROWSER SEARCH
# ============================================================

def make_browser_frame(
    scene,
    index
):

    img = base_canvas()
    draw = ImageDraw.Draw(img)

    draw_top_bar(
        draw,
        "RESEARCH & DISCOVERY"
    )

    draw.text(
        (
            170,
            340
        ),
        "YouTube Search",
        font=FONT_BIG,
        fill=(245, 248, 255)
    )

    rounded_box(
        draw,
        (
            170,
            560,
            3670,
            805
        ),
        48,
        (20, 28, 43),
        outline=(70, 90, 120),
        width=4
    )

    query = clean(
        scene.get(
            "visual_query",
            "AI tools for YouTube creators"
        )
    )

    query = shorten(
        query,
        9
    )

    draw.text(
        (
            250,
            625
        ),
        query,
        font=FONT_BODY,
        fill=(230, 235, 245)
    )

    draw.text(
        (
            3430,
            610
        ),
        "⌕",
        font=FONT_BIG,
        fill=(100, 175, 255)
    )

    results = [
        "AI YouTube workflow",
        "Best AI tools for creators",
        "Automate YouTube with AI",
        "AI video creation workflow"
    ]

    y = 940

    for i, item in enumerate(
        results
    ):

        rounded_box(
            draw,
            (
                190,
                y,
                3600,
                y + 170
            ),
            28,
            (
                (28, 65, 105)
                if i == index % 4
                else (17, 25, 39)
            ),
            outline=(45, 65, 90),
            width=3
        )

        draw.text(
            (
                260,
                y + 48
            ),
            item,
            font=FONT_BODY,
            fill=(235, 240, 248)
        )

        draw.text(
            (
                3220,
                y + 55
            ),
            f"{(87 - i * 11)}%",
            font=FONT_SMALL,
            fill=(110, 190, 255)
        )

        y += 215

    draw_brand(draw)

    return img


# ============================================================
# SCENE TYPE 3 — WORKFLOW
# ============================================================

def make_workflow_frame(
    scene
):

    img = base_canvas()
    draw = ImageDraw.Draw(img)

    draw_top_bar(
        draw,
        "AI CONTENT WORKFLOW"
    )

    steps = [
        "RESEARCH",
        "TOPIC",
        "HOOK",
        "SCRIPT",
        "VOICE",
        "VISUALS",
        "EDIT",
        "UPLOAD"
    ]

    box_w = 780
    box_h = 250

    positions = [
        (180, 430),
        (1530, 430),
        (2880, 430),

        (180, 850),
        (1530, 850),
        (2880, 850),

        (850, 1270),
        (2200, 1270)
    ]

    for i, (
        label,
        pos
    ) in enumerate(
        zip(
            steps,
            positions
        )
    ):

        x, y = pos

        active = (
            i
            == (
                len(steps)
                // 2
            )
        )

        rounded_box(
            draw,
            (
                x,
                y,
                x + box_w,
                y + box_h
            ),
            45,
            (
                (35, 105, 190)
                if active
                else (18, 28, 44)
            ),
            outline=(65, 95, 130),
            width=4
        )

        draw.text(
            (
                x + 55,
                y + 82
            ),
            f"{i + 1:02d}",
            font=FONT_MEDIUM,
            fill=(110, 185, 255)
        )

        draw.text(
            (
                x + 190,
                y + 90
            ),
            label,
            font=FONT_BODY,
            fill=(240, 245, 252)
        )

    draw.text(
        (
            250,
            1730
        ),
        shorten(
            scene.get(
                "on_screen_text",
                "One connected workflow"
            ),
            14
        ),
        font=FONT_BODY,
        fill=(170, 185, 205)
    )

    draw_brand(draw)

    return img


# ============================================================
# SCENE TYPE 4 — AI TOOL CARDS
# ============================================================

def make_tools_frame(
    scene
):

    img = base_canvas()
    draw = ImageDraw.Draw(img)

    draw_top_bar(
        draw,
        "AI TOOL STACK"
    )

    tools = [
        (
            "RESEARCH",
            "Demand"
        ),
        (
            "SCRIPT",
            "Story"
        ),
        (
            "VOICE",
            "Narration"
        ),
        (
            "VISUALS",
            "Scenes"
        ),
        (
            "EDIT",
            "Motion"
        ),
        (
            "UPLOAD",
            "Publish"
        )
    ]

    card_w = 1060
    card_h = 480

    start_x = 160
    start_y = 370

    for i, (
        name,
        desc
    ) in enumerate(
        tools
    ):

        row = i // 3
        col = i % 3

        x = (
            start_x
            + col * 1210
        )

        y = (
            start_y
            + row * 600
        )

        active = (
            i
            == (
                index_from_scene(
                    scene
                )
                % 6
            )
        )

        rounded_box(
            draw,
            (
                x,
                y,
                x + card_w,
                y + card_h
            ),
            50,
            (
                (29, 68, 112)
                if active
                else (17, 27, 42)
            ),
            outline=(
                (80, 145, 220)
                if active
                else (50, 70, 100)
            ),
            width=4
        )

        draw.text(
            (
                x + 65,
                y + 65
            ),
            name,
            font=FONT_MEDIUM,
            fill=(242, 246, 252)
        )

        draw.text(
            (
                x + 65,
                y + 205
            ),
            desc,
            font=FONT_BODY,
            fill=(165, 180, 205)
        )

        draw_chip(
            draw,
            "AI POWERED",
            x + 65,
            y + 325,
            340
        )

    draw_brand(draw)

    return img


def index_from_scene(
    scene
):

    try:
        return int(
            scene.get(
                "scene_number",
                1
            )
        )
    except Exception:
        return 1


# ============================================================
# SCENE TYPE 5 — DASHBOARD / ANALYTICS
# ============================================================

def make_dashboard_frame(
    scene
):

    img = base_canvas()
    draw = ImageDraw.Draw(img)

    draw_top_bar(
        draw,
        "CHANNEL ANALYTICS"
    )

    cards = [
        (
            "VIEWS",
            "128.4K",
            310
        ),
        (
            "WATCH TIME",
            "7.8K",
            1460
        ),
        (
            "SUBSCRIBERS",
            "+4.2K",
            2610
        )
    ]

    for label, value, x in cards:

        rounded_box(
            draw,
            (
                x,
                390,
                x + 950,
                690
            ),
            45,
            (17, 28, 44),
            outline=(55, 80, 110),
            width=4
        )

        draw.text(
            (
                x + 55,
                445
            ),
            label,
            font=FONT_SMALL,
            fill=(145, 165, 190)
        )

        draw.text(
            (
                x + 55,
                525
            ),
            value,
            font=FONT_BIG,
            fill=(240, 245, 252)
        )

    # Chart
    left = 350
    right = 3500
    bottom = 1570
    top = 870

    draw.line(
        [
            (left, bottom),
            (right, bottom)
        ],
        fill=(80, 95, 120),
        width=4
    )

    draw.line(
        [
            (left, top),
            (left, bottom)
        ],
        fill=(80, 95, 120),
        width=4
    )

    points = [
        (430, 1480),
        (850, 1420),
        (1250, 1340),
        (1650, 1210),
        (2050, 1160),
        (2450, 980),
        (2850, 1040),
        (3250, 890),
        (3450, 820)
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
                x - 18,
                y - 18,
                x + 18,
                y + 18
            ),
            fill=(110, 190, 255)
        )

    draw.text(
        (
            350,
            760
        ),
        "GROWTH OVER TIME",
        font=FONT_BODY,
        fill=(225, 232, 242)
    )

    draw_brand(draw)

    return img


# ============================================================
# SCENE TYPE 6 — THUMBNAIL
# ============================================================

def make_thumbnail_frame(
    scene
):

    img = base_canvas()
    draw = ImageDraw.Draw(img)

    draw_top_bar(
        draw,
        "THUMBNAIL + TITLE"
    )

    # Thumbnail
    x1 = 300
    y1 = 450
    x2 = 2350
    y2 = 1640

    rounded_box(
        draw,
        (
            x1,
            y1,
            x2,
            y2
        ),
        40,
        (25, 55, 90),
        outline=(90, 145, 220),
        width=6
    )

    draw.text(
        (
            x1 + 120,
            y1 + 180
        ),
        "AI",
        font=FONT_HUGE,
        fill=(110, 195, 255)
    )

    draw.text(
        (
            x1 + 120,
            y1 + 440
        ),
        "BUILT",
        font=FONT_BIG,
        fill=(245, 248, 255)
    )

    draw.text(
        (
            x1 + 120,
            y1 + 640
        ),
        "MY CHANNEL",
        font=FONT_BIG,
        fill=(245, 248, 255)
    )

    # CTR card
    rounded_box(
        draw,
        (
            2500,
            550,
            3520,
            980
        ),
        45,
        (17, 28, 44),
        outline=(60, 85, 115),
        width=4
    )

    draw.text(
        (
            2580,
            630
        ),
        "CLICK-THROUGH",
        font=FONT_SMALL,
        fill=(145, 165, 190)
    )

    draw.text(
        (
            2580,
            720
        ),
        "↑ 8.7%",
        font=FONT_BIG,
        fill=(100, 210, 155)
    )

    draw.text(
        (
            2580,
            865
        ),
        "Clear promise",
        font=FONT_BODY,
        fill=(220, 230, 242)
    )

    draw.text(
        (
            2580,
            1025
        ),
        "Strong curiosity",
        font=FONT_BODY,
        fill=(220, 230, 242)
    )

    rounded_box(
        draw,
        (
            2500,
            1190,
            3520,
            1450
        ),
        40,
        (35, 95, 180)
    )

    draw.text(
        (
            2600,
            1260
        ),
        "TITLE + THUMBNAIL",
        font=FONT_BODY,
        fill=(245, 248, 255)
    )

    draw_brand(draw)

    return img


# ============================================================
# SCENE TYPE 7 — UPLOAD UI
# ============================================================

def make_upload_frame(
    scene
):

    img = base_canvas()
    draw = ImageDraw.Draw(img)

    draw_top_bar(
        draw,
        "YOUTUBE UPLOAD"
    )

    rounded_box(
        draw,
        (
            280,
            370,
            3560,
            1680
        ),
        50,
        (16, 25, 40),
        outline=(55, 80, 110),
        width=4
    )

    fields = [
        (
            "TITLE",
            shorten(
                package.get(
                    "title",
                    "AI YouTube Automation"
                ),
                12
            ),
            460
        ),
        (
            "DESCRIPTION",
            "AI workflow + tutorial + resources",
            720
        ),
        (
            "HASHTAGS",
            "#AI  #YouTubeAutomation  #AITools",
            980
        ),
        (
            "VISIBILITY",
            "SCHEDULE",
            1240
        )
    ]

    for label, value, y in fields:

        draw.text(
            (
                430,
                y
            ),
            label,
            font=FONT_SMALL,
            fill=(135, 155, 180)
        )

        rounded_box(
            draw,
            (
                850,
                y - 20,
                3300,
                y + 100
            ),
            25,
            (25, 35, 52),
            outline=(50, 70, 95),
            width=2
        )

        draw.text(
            (
                900,
                y + 8
            ),
            value,
            font=FONT_SMALL,
            fill=(225, 232, 242)
        )

    draw_brand(draw)

    return img


# ============================================================
# SCENE TYPE 8 — AUTOMATION
# ============================================================

def make_automation_frame(
    scene
):

    img = base_canvas()
    draw = ImageDraw.Draw(img)

    draw_top_bar(
        draw,
        "AUTOMATION ENGINE"
    )

    nodes = [
        (
            "AI TOPIC",
            300,
            650
        ),
        (
            "SCRIPT",
            1200,
            650
        ),
        (
            "VOICE",
            2100,
            650
        ),
        (
            "VIDEO",
            3000,
            650
        ),
        (
            "YOUTUBE",
            1650,
            1250
        )
    ]

    for i, (
        label,
        x,
        y
    ) in enumerate(
        nodes
    ):

        rounded_box(
            draw,
            (
                x,
                y,
                x + 650,
                y + 230
            ),
            45,
            (
                (30, 82, 140)
                if i == 4
                else (19, 31, 48)
            ),
            outline=(65, 105, 150),
            width=4
        )

        draw.text(
            (
                x + 70,
                y + 75
            ),
            label,
            font=FONT_BODY,
            fill=(240, 245, 252)
        )

    # Connections
    connections = [
        (
            (950, 765),
            (1200, 765)
        ),
        (
            (1850, 765),
            (2100, 765)
        ),
        (
            (2750, 765),
            (3000, 765)
        ),
        (
            (3325, 880),
            (2300, 1250)
        ),
        (
            (1530, 1250),
            (625, 880)
        )
    ]

    for start, end in connections:

        draw.line(
            [
                start,
                end
            ],
            fill=(80, 165, 255),
            width=16
        )

    draw.text(
        (
            1180,
            1690
        ),
        "ONE WORKFLOW  •  DAILY PUBLISHING",
        font=FONT_BODY,
        fill=(160, 180, 205)
    )

    draw_brand(draw)

    return img


# ============================================================
# SCENE TYPE 9 — CTA
# ============================================================

def make_cta_frame():

    img = base_canvas()
    draw = ImageDraw.Draw(img)

    center_text(
        draw,
        "ENJOYED THE VIDEO?",
        390,
        FONT_BIG
    )

    cards = [
        (
            "LIKE",
            350,
            (25, 48, 76)
        ),
        (
            "SHARE",
            1390,
            (25, 48, 76)
        ),
        (
            "SUBSCRIBE",
            2430,
            (185, 45, 58)
        )
    ]

    for label, x, fill in cards:

        rounded_box(
            draw,
            (
                x,
                850,
                x + 850,
                1120
            ),
            60,
            fill,
            outline=(75, 100, 135),
            width=4
        )

        draw.text(
            (
                x + 100,
                920
            ),
            label,
            font=FONT_BODY,
            fill=(250, 250, 255)
        )

    center_text(
        draw,
        "BUILD • CREATE • AUTOMATE",
        1370,
        FONT_MEDIUM,
        (165, 185, 210)
    )

    center_text(
        draw,
        "TECHMIND STUDIO",
        1580,
        FONT_BIG,
        (220, 230, 245)
    )

    return img


# ============================================================
# GENERIC SCENE
# ============================================================

def make_generic_frame(
    scene,
    index
):

    img = base_canvas()
    draw = ImageDraw.Draw(img)

    visual_type = clean(
        scene.get(
            "visual_type",
            "motion_graphic"
        )
    )

    on_screen = clean(
        scene.get(
            "on_screen_text",
            ""
        )
    )

    animation = clean(
        scene.get(
            "animation_direction",
            ""
        )
    )

    draw_top_bar(
        draw,
        visual_type
    )

    center_text(
        draw,
        shorten(
            on_screen
            or "AI CREATOR WORKFLOW",
            8
        ),
        570,
        FONT_BIG
    )

    rounded_box(
        draw,
        (
            420,
            1000,
            3420,
            1480
        ),
        55,
        (17, 28, 44),
        outline=(55, 90, 125),
        width=4
    )

    text_lines = wrap_text(
        draw,
        animation
        or scene.get(
            "narration",
            ""
        ),
        FONT_BODY,
        2600
    )

    y = 1100

    for line in text_lines[:3]:

        center_text(
            draw,
            line,
            y,
            FONT_BODY,
            (190, 205, 225)
        )

        y += 115

    draw_brand(draw)

    return img


# ============================================================
# SCENE DISPATCH
# ============================================================

def make_scene_frame(
    scene,
    index
):

    visual_type = clean(
        scene.get(
            "visual_type",
            ""
        )
    ).lower()

    if (
        "browser" in visual_type
        or "search" in visual_type
    ):
        return make_browser_frame(
            scene,
            index
        )

    if (
        "workflow" in visual_type
        or "diagram" in visual_type
    ):
        return make_workflow_frame(
            scene
        )

    if (
        "tool" in visual_type
        or "comparison" in visual_type
    ):
        return make_tools_frame(
            scene
        )

    if (
        "dashboard" in visual_type
        or "analytics" in visual_type
        or "chart" in visual_type
    ):
        return make_dashboard_frame(
            scene
        )

    if (
        "thumbnail" in visual_type
    ):
        return make_thumbnail_frame(
            scene
        )

    if (
        "youtube" in visual_type
        or "upload" in visual_type
    ):
        return make_upload_frame(
            scene
        )

    if (
        "automation" in visual_type
    ):
        return make_automation_frame(
            scene
        )

    return make_generic_frame(
        scene,
        index
    )


# ============================================================
# CREATE FRAME SET
# ============================================================

print(
    "\n=========================================="
)

print(
    "TECHMIND STUDIO"
)

print(
    "PREMIUM 4K TUTORIAL RENDERER"
)

print(
    "=========================================="
)

hook_path = (
    FRAMES_DIR
    / "000_hook.png"
)

make_hook_frame().save(
    hook_path
)

scene_frames = []

for index, scene in enumerate(
    scenes[:9]
):

    path = (
        FRAMES_DIR
        / f"scene_{index + 1:03d}.png"
    )

    print(
        "Creating visual:",
        index + 1,
        "/",
        min(
            len(scenes),
            9
        )
    )

    frame = make_scene_frame(
        scene,
        index
    )

    frame.save(
        path
    )

    scene_frames.append(
        path
    )


cta_path = (
    FRAMES_DIR
    / "999_cta.png"
)

make_cta_frame().save(
    cta_path
)


# ============================================================
# GENERATE VOICE
# ============================================================

print(
    "\n=========================================="
)

print(
    "GENERATING NATURAL AI VOICE"
)

print(
    "=========================================="
)

run([
    "edge-tts",
    "--voice",
    "en-US-AriaNeural",
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
        "Narration duration could not be detected."
    )

print(
    "Narration duration:",
    round(
        audio_duration,
        2
    ),
    "seconds"
)


# ============================================================
# TARGET DURATION
# ============================================================

target_duration = max(
    MIN_DURATION,
    min(
        MAX_DURATION,
        audio_duration
    )
)

print(
    "Target video duration:",
    round(
        target_duration,
        2
    ),
    "seconds"
)


# ============================================================
# TIMELINE
# ============================================================

timeline = []

# Hook
hook_duration = min(
    8.0,
    target_duration
)

timeline.append(
    (
        hook_path,
        hook_duration,
        "hook"
    )
)

remaining = (
    target_duration
    - hook_duration
)


# ------------------------------------------------------------
# Estimate scene durations from narration word count
# ------------------------------------------------------------

valid_scenes = scenes[:len(scene_frames)]

estimated_scene_durations = []

for scene in valid_scenes:

    narration = clean(
        scene.get(
            "narration",
            ""
        )
    )

    count = max(
        1,
        len(
            words(narration)
        )
    )

    estimated = (
        count
        / 2.45
    )

    estimated = max(
        MIN_VISUAL_DURATION,
        min(
            MAX_VISUAL_DURATION,
            estimated
        )
    )

    estimated_scene_durations.append(
        estimated
    )


total_estimated = sum(
    estimated_scene_durations
)

if total_estimated <= 0:

    total_estimated = (
        len(scene_frames)
        * 10
    )


# Scale durations to remaining time
scale = (
    remaining
    / total_estimated
)


for index, frame_path in enumerate(
    scene_frames
):

    raw_duration = (
        estimated_scene_durations[index]
        * scale
    )

    duration = max(
        MIN_VISUAL_DURATION,
        min(
            MAX_VISUAL_DURATION,
            raw_duration
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
            duration,
            "scene"
        )
    )

    remaining -= duration


# ------------------------------------------------------------
# If time remains, distribute small additional visual segments
# ------------------------------------------------------------

if remaining > 0.5:

    index = 0

    while remaining > 0.5:

        frame_path = scene_frames[
            index
            % len(scene_frames)
        ]

        duration = min(
            MAX_VISUAL_DURATION,
            remaining
        )

        timeline.append(
            (
                frame_path,
                duration,
                "scene_repeat"
            )
        )

        remaining -= duration
        index += 1


# ------------------------------------------------------------
# CTA
# ------------------------------------------------------------

if target_duration >= 190:

    cta_duration = min(
        7.0,
        target_duration * 0.04
    )

    if cta_duration >= 3:

        # Trim timeline from the end
        # so CTA stays inside target duration.
        current_total = sum(
            item[1]
            for item in timeline
        )

        allowed_before_cta = (
            target_duration
            - cta_duration
        )

        new_timeline = []

        used = 0

        for item in timeline:

            if used >= allowed_before_cta:
                break

            duration = min(
                item[1],
                allowed_before_cta - used
            )

            new_timeline.append(
                (
                    item[0],
                    duration,
                    item[2]
                )
            )

            used += duration

        timeline = new_timeline

        timeline.append(
            (
                cta_path,
                cta_duration,
                "cta"
            )
        )


# ============================================================
# FINAL TIMELINE LIMIT
# ============================================================

final_timeline = []

total = 0

for image_path, duration, kind in timeline:

    if total >= target_duration:
        break

    duration = min(
        duration,
        target_duration - total
    )

    if duration <= 0:
        continue

    final_timeline.append(
        (
            image_path,
            duration,
            kind
        )
    )

    total += duration


timeline = final_timeline


print(
    "\n=========================================="
)

print(
    "VISUAL TIMELINE"
)

print(
    "=========================================="
)

for i, (
    path,
    duration,
    kind
) in enumerate(
    timeline
):

    print(
        f"{i + 1:02d}. "
        f"{kind:<15} "
        f"{duration:.2f}s"
    )

print(
    "Total:",
    round(
        sum(
            x[1]
            for x in timeline
        ),
        2
    ),
    "seconds"
)


# ============================================================
# RENDER EACH SEGMENT
# ============================================================

def render_segment(
    image_path,
    output_path,
    duration,
    index
):

    # Very subtle controlled movement.
    # No aggressive shaking.
    if index % 3 == 0:

        zoom_start = 1.000
        zoom_end = 1.008

    elif index % 3 == 1:

        zoom_start = 1.006
        zoom_end = 1.000

    else:

        zoom_start = 1.000
        zoom_end = 1.005

    frames = max(
        1,
        int(
            duration
            * FPS
        )
    )

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


segment_files = []

for index, (
    image_path,
    duration,
    kind
) in enumerate(
    timeline
):

    output = (
        SEGMENTS_DIR
        / f"segment_{index:03d}.mp4"
    )

    print(
        f"\nRendering segment "
        f"{index + 1}/"
        f"{len(timeline)} "
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

with open(
    CONCAT_FILE,
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


print(
    "\n=========================================="
)

print(
    "JOINING VISUAL SEGMENTS"
)

print(
    "=========================================="
)

run([
    "ffmpeg",
    "-y",
    "-f",
    "concat",
    "-safe",
    "0",
    "-i",
    str(CONCAT_FILE),
    "-an",
    "-c",
    "copy",
    str(VISUAL_VIDEO)
])


# ============================================================
# COMBINE VIDEO + VOICE
# ============================================================

print(
    "\n=========================================="
)

print(
    "COMBINING VIDEO + VOICE"
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
    str(VISUAL_VIDEO),
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
        "Final MP4 was not created."
    )

output_duration = probe_duration(
    OUTPUT_FILE
)


print(
    "\n=========================================="
)

print(
    "FINAL VIDEO"
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
    "3840x2160"
)

print(
    "Duration:",
    round(
        output_duration,
        2
    ),
    "seconds"
)

print(
    "Visual segments:",
    len(timeline)
)

print(
    "Maximum visual:",
    round(
        max(
            x[1]
            for x in timeline
        ),
        2
    ),
    "seconds"
)

print(
    "Output:",
    OUTPUT_FILE
)

print(
    "=========================================="
)

print(
    "TECHMIND STUDIO VIDEO READY"
)

print(
    "=========================================="
)
