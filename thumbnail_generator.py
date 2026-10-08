import json
import os
import re
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH = 1280
HEIGHT = 720
OUTPUT = "techmind_studio_thumbnail.png"
PACKAGE_FILE = "content_package.json"


def load_package():
    if not os.path.exists(PACKAGE_FILE):
        raise FileNotFoundError(f"{PACKAGE_FILE} not found.")

    with open(PACKAGE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def clean_title(title):
    title = re.sub(r"[🤖🚀🔥⚡💡🎯📈💻🧠✨😱]", "", title)
    return re.sub(r"\s+", " ", title).strip()


def get_font(size, bold=True):
    fonts = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]
    )

    for path in fonts:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def shorten_text(text, max_words=7):
    words = text.split()
    return (
        text.upper()
        if len(words) <= max_words
        else " ".join(words[:max_words]).upper()
    )


def rounded_rectangle(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(
        box,
        radius=radius,
        fill=fill,
        outline=outline,
        width=width
    )


def create_background():
    img = Image.new("RGB", (WIDTH, HEIGHT), (7, 10, 20))
    pixels = img.load()

    for y in range(HEIGHT):
        for x in range(WIDTH):
            r = int(7 + (x / WIDTH) * 12)
            g = int(10 + (y / HEIGHT) * 8)
            b = int(20 + ((WIDTH - x) / WIDTH) * 18)
            pixels[x, y] = (r, g, b)

    return img


def add_glow(img):
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)

    draw.ellipse(
        (760, 80, 1190, 510),
        fill=(0, 180, 255, 80)
    )

    draw.ellipse(
        (900, 250, 1300, 650),
        fill=(120, 40, 255, 55)
    )

    glow = glow.filter(ImageFilter.GaussianBlur(90))

    return Image.alpha_composite(
        img.convert("RGBA"),
        glow
    ).convert("RGB")


def draw_ai_visual(draw):
    cx, cy = 1010, 355

    for radius, width in [
        (190, 5),
        (155, 3),
        (120, 2)
    ]:
        draw.ellipse(
            (
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius
            ),
            outline=(40, 190, 255),
            width=width
        )

    nodes = [
        (900, 250),
        (1090, 240),
        (1160, 350),
        (1080, 470),
        (900, 460),
        (850, 350),
    ]

    for nx, ny in nodes:
        draw.line(
            (cx, cy, nx, ny),
            fill=(50, 180, 255),
            width=4
        )

        draw.ellipse(
            (nx - 12, ny - 12, nx + 12, ny + 12),
            fill=(30, 150, 255),
            outline=(220, 250, 255),
            width=3
        )

    draw.ellipse(
        (cx - 72, cy - 72, cx + 72, cy + 72),
        fill=(12, 25, 48),
        outline=(70, 210, 255),
        width=6
    )

    font = get_font(54, True)

    bbox = draw.textbbox((0, 0), "AI", font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    draw.text(
        (cx - tw / 2, cy - th / 2 - 5),
        "AI",
        font=font,
        fill=(235, 250, 255)
    )


def draw_youtube_card(draw):
    x1, y1 = 790, 535
    x2, y2 = 1190, 635

    rounded_rectangle(
        draw,
        (x1, y1, x2, y2),
        20,
        fill=(15, 20, 32),
        outline=(55, 70, 95),
        width=2
    )

    draw.rounded_rectangle(
        (x1 + 20, y1 + 20, x1 + 82, y1 + 80),
        radius=16,
        fill=(220, 30, 45)
    )

    draw.polygon(
        [
            (x1 + 44, y1 + 34),
            (x1 + 44, y1 + 66),
            (x1 + 68, y1 + 50)
        ],
        fill=(255, 255, 255)
    )

    font = get_font(24, True)

    draw.text(
        (x1 + 105, y1 + 18),
        "TECHMIND STUDIO",
        font=font,
        fill=(245, 248, 255)
    )

    small = get_font(18, False)

    draw.text(
        (x1 + 105, y1 + 53),
        "AI • YouTube • Automation",
        font=small,
        fill=(150, 165, 185)
    )


def generate_thumbnail(package):
    title = clean_title(
        package.get(
            "title",
            "AI YOUTUBE AUTOMATION"
        )
    )

    headline = shorten_text(title, 7)

    img = create_background()
    img = add_glow(img)

    draw = ImageDraw.Draw(img)

    brand_font = get_font(24, True)

    draw.text(
        (55, 42),
        "TECHMIND STUDIO",
        font=brand_font,
        fill=(90, 205, 255)
    )

    headline_font = get_font(64, True)

    words = headline.split()

    if len(words) > 4:
        split_at = len(words) // 2
        line1 = " ".join(words[:split_at])
        line2 = " ".join(words[split_at:])
    else:
        line1 = headline
        line2 = ""

    draw.text(
        (55, 135),
        line1,
        font=headline_font,
        fill=(255, 255, 255)
    )

    if line2:
        draw.text(
            (55, 215),
            line2,
            font=headline_font,
            fill=(70, 205, 255)
        )

    rounded_rectangle(
        draw,
        (55, 325, 390, 385),
        18,
        fill=(220, 40, 55)
    )

    badge_font = get_font(27, True)

    draw.text(
        (78, 339),
        "WATCH THIS",
        font=badge_font,
        fill=(255, 255, 255)
    )

    support_font = get_font(22, False)

    draw.text(
        (58, 425),
        "AI • AUTOMATION • YOUTUBE",
        font=support_font,
        fill=(170, 185, 205)
    )

    cards = [
        ("SCRIPT", 55),
        ("VOICE", 190),
        ("VIDEO", 325),
        ("UPLOAD", 460),
    ]

    card_font = get_font(17, True)

    for label, x in cards:
        rounded_rectangle(
            draw,
            (x, 505, x + 120, 555),
            14,
            fill=(16, 24, 40),
            outline=(45, 70, 100),
            width=2
        )

        draw.text(
            (x + 17, 521),
            label,
            font=card_font,
            fill=(220, 235, 250)
        )

    draw_ai_visual(draw)
    draw_youtube_card(draw)

    draw.line(
        (55, 670, 1225, 670),
        fill=(35, 150, 220),
        width=3
    )

    img.save(
        OUTPUT,
        "PNG",
        optimize=True
    )

    print("==========================================")
    print("Thumbnail generated successfully.")
    print("Title:", title)
    print("Thumbnail:", OUTPUT)
    print("Size:", f"{WIDTH}x{HEIGHT}")
    print("==========================================")


if __name__ == "__main__":
    package = load_package()
    generate_thumbnail(package)
