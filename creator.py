import os
import re
import json
import time
import requests
import xml.etree.ElementTree as ET
from pathlib import Path


# ============================================================
# TECHMIND STUDIO — AI CONTENT CREATOR
# ============================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing.")

PACKAGE_FILE = Path("content_package.json")
STATE_FILE = Path("automation_state.json")

CHANNEL_NAME = "TechMind Studio"

# IMPORTANT:
# Quota-exhausted models are skipped immediately.
# Do NOT keep retrying a 429 model.
MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
]


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    value = str(value)

    value = value.replace("\r", " ")
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def get_news():
    feeds = [
        (
            "https://news.google.com/rss/search?"
            "q=AI+artificial+intelligence+when:1d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
        (
            "https://news.google.com/rss/search?"
            "q=generative+AI+technology+when:1d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
        (
            "https://news.google.com/rss/search?"
            "q=AI+tools+YouTube+creator+when:1d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    ]

    results = []
    seen = set()

    for feed_url in feeds:
        try:
            response = requests.get(
                feed_url,
                timeout=30,
                headers={
                    "User-Agent": "TechMindStudio/1.0"
                },
            )

            response.raise_for_status()

            root = ET.fromstring(response.text)

            for item in root.findall(".//item"):
                title = clean_text(
                    item.findtext("title")
                )

                link = clean_text(
                    item.findtext("link")
                )

                description = clean_text(
                    item.findtext("description")
                )

                if not title:
                    continue

                key = title.lower()

                if key in seen:
                    continue

                seen.add(key)

                results.append({
                    "title": title,
                    "link": link,
                    "description": description[:800],
                })

        except Exception as error:
            print(
                "News feed error:",
                repr(error)
            )

    return results[:60]


# ============================================================
# JSON EXTRACTION / REPAIR
# ============================================================

def extract_json(text):
    if not text:
        raise ValueError(
            "Gemini returned empty response."
        )

    text = str(text).strip()

    # Remove markdown fences.
    text = re.sub(
        r"```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"```\s*",
        "",
        text
    )

    start = text.find("{")

    if start == -1:
        raise ValueError(
            "No JSON object found."
        )

    depth = 0
    in_string = False
    escaped = False

    for i in range(start, len(text)):

        char = text[i]

        if escaped:
            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1

        elif char == "}":
            depth -= 1

            if depth == 0:
                return text[start:i + 1]

    # Last fallback.
    end = text.rfind("}")

    if end != -1:
        return text[start:end + 1]

    raise ValueError(
        "Incomplete JSON returned by Gemini."
    )


def parse_json(text):
    extracted = extract_json(text)

    # Attempt 1 — normal JSON.
    try:
        return json.loads(extracted)
    except Exception as error:
        print(
            "Normal JSON parse failed:",
            error
        )

    # Attempt 2 — remove trailing commas.
    repaired = re.sub(
        r",\s*([}\]])",
        r"\1",
        extracted
    )

    try:
        return json.loads(repaired)
    except Exception as error:
        print(
            "Repaired JSON parse failed:",
            error
        )

    # Attempt 3 — quote common unquoted keys.
    repaired = re.sub(
        r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:',
        r'\1"\2":',
        repaired
    )

    try:
        return json.loads(repaired)
    except Exception as error:
        print(
            "Final JSON parse failed:",
            error
        )

    raise ValueError(
        "Gemini returned invalid JSON."
    )


# ============================================================
# GEMINI
# ============================================================

def call_gemini(model, prompt):
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
            "temperature": 0.75,
            "maxOutputTokens": 9000,
            "responseMimeType": "application/json",
        },
    }

    response = requests.post(
        url,
        headers={
            "x-goog-api-key": GEMINI_API_KEY,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )

    print(
        "Gemini HTTP:",
        response.status_code
    )

    if response.status_code != 200:
        print(
            response.text[:2500]
        )

        raise RuntimeError(
            f"Gemini HTTP {response.status_code}"
        )

    data = response.json()

    candidates = data.get(
        "candidates",
        []
    )

    if not candidates:
        raise RuntimeError(
            "Gemini returned no candidates."
        )

    parts = (
        candidates[0]
        .get("content", {})
        .get("parts", [])
    )

    output = ""

    for part in parts:
        if "text" in part:
            output += str(
                part["text"]
            )

    if not output.strip():
        raise RuntimeError(
            "Gemini returned empty text."
        )

    return parse_json(output)


def generate_content(prompt):
    last_error = None

    for index, model in enumerate(
        MODELS,
        start=1
    ):
        print("")
        print(
            f"Gemini attempt {index}/{len(MODELS)}..."
        )
        print(
            "Model:",
            model
        )

        try:
            result = call_gemini(
                model,
                prompt
            )

            print(
                "Gemini generation successful."
            )

            return result

        except RuntimeError as error:

            last_error = error

            error_text = str(error)

            # 429 = quota. Do not retry same model.
            if "429" in error_text:
                print(
                    "Quota exceeded for this model."
                )
                print(
                    "Skipping immediately."
                )
                continue

            # 503 = temporary availability.
            if "503" in error_text:
                print(
                    "Model temporarily unavailable."
                )
                print(
                    "Moving to next model."
                )
                time.sleep(2)
                continue

            print(
                "Generation failed:",
                error
            )

            continue

        except Exception as error:

            last_error = error

            print(
                "Generation failed:",
                repr(error)
            )

            continue

    raise RuntimeError(
        "All Gemini attempts failed: "
        + str(last_error)
    )


# ============================================================
# LOAD AUTOMATION STATE
# ============================================================

previous_topics = []

if STATE_FILE.exists():
    try:
        state = json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

        previous_topics = state.get(
            "previous_topics",
            []
        )

        if not isinstance(
            previous_topics,
            list
        ):
            previous_topics = []

    except Exception:
        previous_topics = []


print("")
print(
    "================================================"
)
print(
    "TechMind Studio - Automation Engine"
)
print(
    "================================================"
)

print(
    "Previous topics:",
    len(previous_topics)
)


# ============================================================
# NEWS
# ============================================================

print(
    "Fetching fresh AI news..."
)

news = get_news()

print(
    "Found",
    len(news),
    "headlines."
)

if not news:
    raise RuntimeError(
        "No fresh AI news found."
    )


# ============================================================
# NEWS FORMAT
# ============================================================

news_text = "\n\n".join(
    [
        (
            f"HEADLINE: {item['title']}\n"
            f"DESCRIPTION: {item['description']}\n"
            f"URL: {item['link']}"
        )
        for item in news
    ]
)


previous_text = "\n".join(
    [
        "- " + clean_text(topic)
        for topic in previous_topics[-30:]
    ]
)

if not previous_text:
    previous_text = "None"


# ============================================================
# PROMPT
# ============================================================

prompt = f"""
You are the senior AI YouTube producer for
{CHANNEL_NAME}.

Create ONE completely original YouTube video package.

CHANNEL:
{CHANNEL_NAME}

CONTENT DIRECTION:
AI, artificial intelligence, AI tools,
YouTube automation, creator experiments,
AI tutorials and useful technology.

The video should feel like a premium technology
YouTube video.

DO NOT create:
- animal content
- anime content
- generic motivation
- copied YouTube scripts
- fake claims
- boring slideshow content

CURRENT AI NEWS:

{news_text}

PREVIOUS TOPICS:

{previous_text}

Choose a FRESH topic that is meaningfully different
from previous topics.

==================================================
LONG VIDEO
==================================================

Target duration:
3 minutes 15 seconds to 3 minutes 45 seconds.

Target spoken words:
approximately 470-530 words.

Create EXACTLY 9 scenes.

Structure:

Scene 1:
Powerful hook.

Scene 2:
Problem / opportunity.

Scene 3:
Discovery / explanation.

Scene 4:
Step-by-step process.

Scene 5:
Practical example.

Scene 6:
Tools / workflow.

Scene 7:
Results / comparison.

Scene 8:
Key takeaway.

Scene 9:
Conclusion + natural CTA.

Every scene must contain:

scene_number
scene_title
narration
visual_query
visual_type
on_screen_text
animation_direction
key_visuals

VISUAL TYPES should be useful for a professional
motion-graphics renderer.

Examples:

browser_ui
dashboard
motion_graphic
animated_chart
workflow_diagram
comparison_cards
thumbnail_mockup
youtube_ui
cinematic_title
cta

Do NOT make every scene the same visual type.

Each visual must directly match the narration.

==================================================
HOOK
==================================================

The first 5-10 seconds must immediately create
curiosity.

Avoid:
"Today we are going to talk about..."

Prefer:
a surprising result,
strong question,
challenge,
experiment,
or unexpected fact.

==================================================
TITLE
==================================================

Under 100 characters.

Include 1-2 relevant emojis.

Examples of relevant emoji:
🤖
🔥
🚀
💡
⚡
🎯

Do not use random emojis.

==================================================
DESCRIPTION
==================================================

Create a professional YouTube description.

Include:
- what viewers will learn
- useful context
- natural CTA
- relevant hashtags

==================================================
HASHTAGS
==================================================

Create 5-8 relevant hashtags.

==================================================
YOUTUBE TAGS
==================================================

Create 10-15 useful search tags.

==================================================
SHORT
==================================================

Also create a Short based on the same topic.

Create EXACTLY 4 short scenes.

Total Short narration:
approximately 80-120 words.

The Short needs:
- strong first sentence
- fast pacing
- useful information
- clear ending
- vertical-friendly visual ideas

==================================================
IMPORTANT JSON RULES
==================================================

Return ONLY valid JSON.

No markdown.
No ```json.
No explanation outside JSON.

Use double quotes for all JSON keys
and string values.

Escape quotation marks inside strings.

JSON schema:

{{
  "topic": "...",
  "source_url": "...",
  "title": "...",
  "description": "...",
  "hashtags": [
    "#AI",
    "#ArtificialIntelligence"
  ],
  "tags": [
    "AI",
    "artificial intelligence"
  ],
  "script_word_count": 500,

  "scenes": [
    {{
      "scene_number": 1,
      "scene_title": "...",
      "narration": "...",
      "visual_query": "...",
      "visual_type": "cinematic_title",
      "on_screen_text": "...",
      "animation_direction": "...",
      "key_visuals": [
        "...",
        "..."
      ]
    }}
  ],

  "short_scenes": [
    {{
      "scene_number": 1,
      "scene_title": "...",
      "narration": "...",
      "visual_query": "...",
      "visual_type": "motion_graphic",
      "on_screen_text": "...",
      "animation_direction": "...",
      "key_visuals": [
        "...",
        "..."
      ]
    }}
  ]
}}
"""


# ============================================================
# GENERATE
# ============================================================

print(
    "Generating a NEW topic..."
)

package = generate_content(
    prompt
)


# ============================================================
# VALIDATION
# ============================================================

if not isinstance(
    package,
    dict
):
    raise RuntimeError(
        "Gemini result is not a JSON object."
    )


required = [
    "topic",
    "title",
    "description",
    "hashtags",
    "tags",
    "scenes",
    "short_scenes",
]


for field in required:
    if field not in package:
        raise RuntimeError(
            "Missing field: "
            + field
        )


scenes = package.get(
    "scenes",
    []
)

short_scenes = package.get(
    "short_scenes",
    []
)


if len(scenes) != 9:
    raise RuntimeError(
        "Expected exactly 9 scenes, got "
        + str(len(scenes))
    )


if len(short_scenes) != 4:
    raise RuntimeError(
        "Expected exactly 4 short scenes, got "
        + str(len(short_scenes))
    )


# ============================================================
# NORMALIZE TITLE
# ============================================================

title = clean_text(
    package["title"]
)

if len(title) > 100:
    title = title[:97].rstrip() + "..."


package["title"] = title


# ============================================================
# NORMALIZE HASHTAGS
# ============================================================

hashtags = package.get(
    "hashtags",
    []
)

if not isinstance(
    hashtags,
    list
):
    hashtags = []

clean_hashtags = []

for tag in hashtags:

    tag = clean_text(tag)

    if not tag:
        continue

    if not tag.startswith("#"):
        tag = "#" + tag

    if tag not in clean_hashtags:
        clean_hashtags.append(tag)


if "#AI" not in clean_hashtags:
    clean_hashtags.insert(
        0,
        "#AI"
    )


package["hashtags"] = (
    clean_hashtags[:8]
)


# ============================================================
# NORMALIZE TAGS
# ============================================================

tags = package.get(
    "tags",
    []
)

if not isinstance(
    tags,
    list
):
    tags = []

clean_tags = []

for tag in tags:

    tag = clean_text(tag)

    if (
        tag
        and tag not in clean_tags
    ):
        clean_tags.append(tag)


package["tags"] = (
    clean_tags[:15]
)


# ============================================================
# NORMALIZE SCENES
# ============================================================

for index, scene in enumerate(
    scenes,
    start=1
):

    scene["scene_number"] = index

    scene["scene_title"] = clean_text(
        scene.get(
            "scene_title",
            f"Scene {index}"
        )
    )

    scene["narration"] = clean_text(
        scene.get(
            "narration",
            ""
        )
    )

    scene["visual_query"] = clean_text(
        scene.get(
            "visual_query",
            scene["scene_title"]
        )
    )

    scene["visual_type"] = clean_text(
        scene.get(
            "visual_type",
            "motion_graphic"
        )
    )

    scene["on_screen_text"] = clean_text(
        scene.get(
            "on_screen_text",
            ""
        )
    )

    scene["animation_direction"] = clean_text(
        scene.get(
            "animation_direction",
            "subtle professional motion"
        )
    )

    key_visuals = scene.get(
        "key_visuals",
        []
    )

    if not isinstance(
        key_visuals,
        list
    ):
        key_visuals = []

    scene["key_visuals"] = [
        clean_text(item)
        for item in key_visuals
        if clean_text(item)
    ]


# ============================================================
# NORMALIZE SHORT SCENES
# ============================================================

for index, scene in enumerate(
    short_scenes,
    start=1
):

    scene["scene_number"] = index

    scene["scene_title"] = clean_text(
        scene.get(
            "scene_title",
            f"Short Scene {index}"
        )
    )

    scene["narration"] = clean_text(
        scene.get(
            "narration",
            ""
        )
    )

    scene["visual_query"] = clean_text(
        scene.get(
            "visual_query",
            scene["scene_title"]
        )
    )

    scene["visual_type"] = clean_text(
        scene.get(
            "visual_type",
            "motion_graphic"
        )
    )

    scene["on_screen_text"] = clean_text(
        scene.get(
            "on_screen_text",
            ""
        )
    )

    scene["animation_direction"] = clean_text(
        scene.get(
            "animation_direction",
            "fast modern motion"
        )
    )

    key_visuals = scene.get(
        "key_visuals",
        []
    )

    if not isinstance(
        key_visuals,
        list
    ):
        key_visuals = []

    scene["key_visuals"] = [
        clean_text(item)
        for item in key_visuals
        if clean_text(item)
    ]


# ============================================================
# WORD COUNT
# ============================================================

full_script = " ".join(
    scene["narration"]
    for scene in scenes
)

word_count = len(
    full_script.split()
)

package["script_word_count"] = (
    word_count
)


if word_count < 400:
    print(
        "WARNING: Script is shorter than target:",
        word_count
    )

if word_count > 600:
    print(
        "WARNING: Script is longer than target:",
        word_count
    )


# ============================================================
# SOURCE
# ============================================================

source_url = clean_text(
    package.get(
        "source_url",
        ""
    )
)

if not source_url:

    source_url = news[0].get(
        "link",
        ""
    )

package["source_url"] = source_url


# ============================================================
# SAVE PACKAGE
# ============================================================

PACKAGE_FILE.write_text(
    json.dumps(
        package,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)


# ============================================================
# AUTOMATION STATE
# ============================================================

topic = clean_text(
    package["topic"]
)

if topic and topic not in previous_topics:

    previous_topics.append(
        topic
    )


# Keep state manageable.
previous_topics = (
    previous_topics[-100:]
)

state = {
    "channel": CHANNEL_NAME,
    "previous_topics": previous_topics,
    "last_topic": topic,
    "last_title": package["title"],
    "last_script_word_count": word_count,
}


STATE_FILE.write_text(
    json.dumps(
        state,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)


# ============================================================
# FINAL OUTPUT
# ============================================================

print("")
print(
    "================================================"
)
print(
    "CONTENT PACKAGE CREATED SUCCESSFULLY"
)
print(
    "================================================"
)

print(
    "Topic:",
    package["topic"]
)

print(
    "Title:",
    package["title"]
)

print(
    "Script words:",
    word_count
)

print(
    "Scenes:",
    len(scenes)
)

print(
    "Short scenes:",
    len(short_scenes)
)

print(
    "Hashtags:",
    " ".join(
        package["hashtags"]
    )
)

print(
    "Tags:",
    len(
        package["tags"]
    )
)

print(
    "Saved:",
    PACKAGE_FILE
)

print(
    "================================================"
)
