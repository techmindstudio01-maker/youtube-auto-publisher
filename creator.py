import os
import re
import json
import time
import requests
import xml.etree.ElementTree as ET
from pathlib import Path


# ============================================================
# TECHMIND STUDIO
# AI CONTENT CREATOR
# ============================================================

CHANNEL_NAME = "TechMind Studio"

GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY",
    ""
).strip()

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing."
    )

PACKAGE_FILE = Path(
    "content_package.json"
)

STATE_FILE = Path(
    "automation_state.json"
)


# ============================================================
# GEMINI MODELS
# ============================================================

# Primary model is the one that previously returned HTTP 200.
# 429 models are skipped immediately.
MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
]


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    value = str(value)

    value = value.replace(
        "\r",
        " "
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


def word_count(text):
    return len(
        clean_text(text).split()
    )


# ============================================================
# NEWS
# ============================================================

def fetch_news():

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

    for url in feeds:

        try:

            response = requests.get(
                url,
                timeout=30,
                headers={
                    "User-Agent":
                    "TechMindStudio/1.0"
                }
            )

            response.raise_for_status()

            root = ET.fromstring(
                response.text
            )

            for item in root.findall(
                ".//item"
            ):

                title = clean_text(
                    item.findtext(
                        "title"
                    )
                )

                link = clean_text(
                    item.findtext(
                        "link"
                    )
                )

                description = clean_text(
                    item.findtext(
                        "description"
                    )
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
                    "description":
                        description[:1000]
                })

        except Exception as error:

            print(
                "News feed error:",
                repr(error)
            )

    return results[:80]


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(text):

    if not text:
        raise ValueError(
            "Gemini returned empty text."
        )

    text = str(text).strip()

    # Remove markdown fences.
    text = re.sub(
        r"```json",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"```",
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

    for index in range(
        start,
        len(text)
    ):

        char = text[index]

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
                return text[
                    start:index + 1
                ]

    end = text.rfind("}")

    if end != -1:
        return text[
            start:end + 1
        ]

    raise ValueError(
        "Incomplete JSON."
    )


def parse_json(text):

    extracted = extract_json(
        text
    )

    # Normal JSON.
    try:
        return json.loads(
            extracted
        )

    except Exception as error:

        print(
            "Normal JSON failed:",
            error
        )

    # Remove trailing commas.
    repaired = re.sub(
        r",\s*([}\]])",
        r"\1",
        extracted
    )

    try:
        return json.loads(
            repaired
        )

    except Exception as error:

        print(
            "Trailing-comma repair failed:",
            error
        )

    # Common unquoted-key repair.
    repaired = re.sub(
        r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:',
        r'\1"\2":',
        repaired
    )

    try:
        return json.loads(
            repaired
        )

    except Exception as error:

        print(
            "Final JSON repair failed:",
            error
        )

    raise ValueError(
        "Gemini returned invalid JSON."
    )


# ============================================================
# GEMINI API
# ============================================================

def gemini_request(
    model,
    prompt
):

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
            "responseMimeType":
                "application/json"
        }
    }

    response = requests.post(
        url,
        headers={
            "Content-Type":
                "application/json",
            "x-goog-api-key":
                GEMINI_API_KEY
        },
        json=payload,
        timeout=120
    )

    print(
        "Gemini HTTP:",
        response.status_code
    )

    if response.status_code != 200:

        print(
            response.text[:2000]
        )

        raise RuntimeError(
            f"Gemini HTTP "
            f"{response.status_code}"
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

    text = ""

    for part in parts:

        if "text" in part:

            text += str(
                part["text"]
            )

    if not text.strip():
        raise RuntimeError(
            "Gemini returned empty text."
        )

    return parse_json(
        text
    )


def generate_with_gemini(
    prompt
):

    last_error = None

    for number, model in enumerate(
        MODELS,
        start=1
    ):

        print("")
        print(
            f"Gemini attempt "
            f"{number}/{len(MODELS)}..."
        )

        print(
            "Model:",
            model
        )

        try:

            result = gemini_request(
                model,
                prompt
            )

            print(
                "Gemini generation successful."
            )

            return result

        except RuntimeError as error:

            last_error = error

            error_text = str(
                error
            )

            # ------------------------------------------------
            # 429 QUOTA
            # ------------------------------------------------

            if "429" in error_text:

                print(
                    "429 quota exceeded."
                )

                print(
                    "Skipping this model immediately."
                )

                continue

            # ------------------------------------------------
            # 503 TEMPORARY
            # ------------------------------------------------

            if "503" in error_text:

                print(
                    "503 temporary model issue."
                )

                print(
                    "Moving to next model."
                )

                time.sleep(2)

                continue

            # ------------------------------------------------
            # 404
            # ------------------------------------------------

            if "404" in error_text:

                print(
                    "404 model unavailable."
                )

                print(
                    "Moving to next model."
                )

                continue

            print(
                "Generation failed:",
                error
            )

        except Exception as error:

            last_error = error

            print(
                "Unexpected Gemini error:",
                repr(error)
            )

    raise RuntimeError(
        "All Gemini attempts failed: "
        + str(last_error)
    )


# ============================================================
# AUTOMATION STATE
# ============================================================

def load_state():

    if not STATE_FILE.exists():
        return {
            "previous_topics": []
        }

    try:

        data = json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(
            data,
            dict
        ):
            return {
                "previous_topics": []
            }

        topics = data.get(
            "previous_topics",
            []
        )

        if not isinstance(
            topics,
            list
        ):
            topics = []

        data["previous_topics"] = topics

        return data

    except Exception:

        return {
            "previous_topics": []
        }


state = load_state()

previous_topics = state.get(
    "previous_topics",
    []
)


# ============================================================
# NEWS
# ============================================================

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

print(
    "Fetching fresh AI news..."
)

news = fetch_news()

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
# NEWS CONTEXT
# ============================================================

news_context = []

for item in news:

    news_context.append(
        (
            "HEADLINE: "
            + item["title"]
            + "\nDESCRIPTION: "
            + item["description"]
            + "\nURL: "
            + item["link"]
        )
    )


news_text = "\n\n".join(
    news_context
)


previous_text = "\n".join(
    [
        "- " + clean_text(topic)
        for topic in previous_topics[-40:]
    ]
)

if not previous_text:
    previous_text = "None"


# ============================================================
# CONTENT PROMPT
# ============================================================

prompt = f"""
You are the senior YouTube content producer
for {CHANNEL_NAME}.

Create ONE original premium AI/technology
YouTube video package.

CHANNEL:
{CHANNEL_NAME}

CURRENT NEWS:

{news_text}

PREVIOUS TOPICS:

{previous_text}

==================================================
TOPIC
==================================================

Choose ONE fresh topic.

It must be meaningfully different from previous
topics.

Preferred subjects:

- AI tools
- AI automation
- AI agents
- YouTube creator workflows
- AI productivity
- AI business
- generative AI
- new AI technology
- practical AI experiments
- AI tutorials
- AI creator economy

Avoid:

- animals
- anime
- generic motivation
- fake news
- copied videos
- boring generic explanations

==================================================
LONG VIDEO
==================================================

Target:

3 minutes 15 seconds to 3 minutes 45 seconds.

Target narration:

470-530 words.

Create EXACTLY 9 scenes.

The story structure:

1. Powerful hook
2. Problem/opportunity
3. Discovery
4. Step-by-step explanation
5. Practical example
6. Tool/workflow
7. Result/comparison
8. Key lesson
9. Conclusion + CTA

The narration must sound natural when spoken.

Do NOT write:

"Today we are going to talk about..."

Start with curiosity, a result, a challenge,
or a surprising statement.

==================================================
VISUALS
==================================================

Every scene needs a visual that directly matches
its narration.

Use different visual types.

Possible visual types:

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

Do NOT make every scene identical.

==================================================
TITLE
==================================================

Under 100 characters.

Use 1-2 relevant emojis.

Examples:

🤖
🔥
🚀
💡
⚡
🎯

==================================================
DESCRIPTION
==================================================

Professional YouTube description.

Explain what the viewer will learn.

Include a natural CTA.

==================================================
HASHTAGS
==================================================

5-8 hashtags.

==================================================
YOUTUBE TAGS
==================================================

10-15 tags.

==================================================
SHORT
==================================================

Create EXACTLY 4 Short scenes.

Short narration:

80-120 words total.

The Short must have:

- strong opening
- fast useful information
- clear takeaway
- strong ending

==================================================
IMPORTANT
==================================================

Return ONLY valid JSON.

No markdown.

No ```json.

No explanation.

Use double quotes.

JSON structure:

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
    "artificial intelligence",
    "AI tools"
  ],

  "script": "...",

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

CRITICAL:

The "script" field must contain the COMPLETE
long-video narration.

The scene narration fields must contain the
same narration divided across the 9 scenes.

The total script should be 470-530 words.

The JSON must be valid.
"""


# ============================================================
# GENERATE
# ============================================================

print(
    "Generating a NEW topic..."
)

data = generate_with_gemini(
    prompt
)


# ============================================================
# VALIDATE BASIC FIELDS
# ============================================================

required_fields = [
    "topic",
    "title",
    "description",
    "hashtags",
    "tags",
    "script",
    "scenes",
    "short_scenes"
]

for field in required_fields:

    if field not in data:

        raise RuntimeError(
            "Missing content field: "
            + field
        )


# ============================================================
# NORMALIZE SCRIPT
# ============================================================

script = clean_text(
    data.get("script", "")
)


scenes = data.get(
    "scenes",
    []
)

if not isinstance(
    scenes,
    list
):
    scenes = []


# ------------------------------------------------------------
# If Gemini forgot script but provided scene narration,
# rebuild the script automatically.
# ------------------------------------------------------------

if word_count(script) < 50:

    scene_narration = []

    for scene in scenes:

        narration = clean_text(
            scene.get(
                "narration",
                ""
            )
        )

        if narration:
            scene_narration.append(
                narration
            )

    script = " ".join(
        scene_narration
    )


if word_count(script) < 100:

    raise RuntimeError(
        "Generated script is too short."
    )


data["script"] = script


# ============================================================
# EXACT 9 LONG SCENES
# ============================================================

if len(scenes) != 9:

    raise RuntimeError(
        "Expected exactly 9 long scenes, got "
        + str(len(scenes))
    )


for index, scene in enumerate(
    scenes,
    start=1
):

    if not isinstance(
        scene,
        dict
    ):
        raise RuntimeError(
            f"Scene {index} is invalid."
        )

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
            ""
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
            "professional subtle motion"
        )
    )

    visuals = scene.get(
        "key_visuals",
        []
    )

    if not isinstance(
        visuals,
        list
    ):
        visuals = []

    scene["key_visuals"] = [
        clean_text(item)
        for item in visuals
        if clean_text(item)
    ]

    if not scene["narration"]:

        raise RuntimeError(
            f"Scene {index} has no narration."
        )

    if not scene["visual_query"]:

        scene["visual_query"] = (
            data["topic"]
            + " technology"
        )


# ============================================================
# SHORT SCENES
# ============================================================

short_scenes = data.get(
    "short_scenes",
    []
)

if not isinstance(
    short_scenes,
    list
):
    short_scenes = []


if len(short_scenes) != 4:

    raise RuntimeError(
        "Expected exactly 4 short scenes, got "
        + str(len(short_scenes))
    )


for index, scene in enumerate(
    short_scenes,
    start=1
):

    if not isinstance(
        scene,
        dict
    ):
        raise RuntimeError(
            f"Short scene {index} is invalid."
        )

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
            data["topic"] + " technology"
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
            "fast professional motion"
        )
    )

    visuals = scene.get(
        "key_visuals",
        []
    )

    if not isinstance(
        visuals,
        list
    ):
        visuals = []

    scene["key_visuals"] = [
        clean_text(item)
        for item in visuals
        if clean_text(item)
    ]

    if not scene["narration"]:

        raise RuntimeError(
            f"Short scene {index} has no narration."
        )


# ============================================================
# TITLE
# ============================================================

title = clean_text(
    data["title"]
)

if len(title) > 100:

    title = (
        title[:97].rstrip()
        + "..."
    )

data["title"] = title


# ============================================================
# HASHTAGS
# ============================================================

hashtags = data.get(
    "hashtags",
    []
)

if not isinstance(
    hashtags,
    list
):
    hashtags = []


clean_hashtags = []

for hashtag in hashtags:

    hashtag = clean_text(
        hashtag
    )

    if not hashtag:
        continue

    if not hashtag.startswith("#"):

        hashtag = "#" + hashtag

    if hashtag not in clean_hashtags:

        clean_hashtags.append(
            hashtag
        )


if "#AI" not in clean_hashtags:

    clean_hashtags.insert(
        0,
        "#AI"
    )


data["hashtags"] = (
    clean_hashtags[:8]
)


# ============================================================
# TAGS
# ============================================================

tags = data.get(
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

    tag = clean_text(
        tag
    )

    if (
        tag
        and tag not in clean_tags
    ):

        clean_tags.append(
            tag
        )


data["tags"] = (
    clean_tags[:15]
)


# ============================================================
# DESCRIPTION
# ============================================================

description = clean_text(
    data["description"]
)

hashtag_text = " ".join(
    data["hashtags"]
)

if hashtag_text:

    if hashtag_text not in description:

        description += (
            "\n\n"
            + hashtag_text
        )


data["description"] = description


# ============================================================
# SOURCE URL
# ============================================================

source_url = clean_text(
    data.get(
        "source_url",
        ""
    )
)

if not source_url and news:

    source_url = news[0].get(
        "link",
        ""
    )


data["source_url"] = source_url


# ============================================================
# COMPATIBILITY FIELDS
# ============================================================

# Current renderer expects "script".
# Older renderer versions expect "long_scenes".
# Workflow expects "scenes".
# We provide ALL THREE.

data["long_scenes"] = scenes

data["scenes"] = scenes

data["short_scenes"] = short_scenes


# ============================================================
# WORD COUNT
# ============================================================

script_words = word_count(
    data["script"]
)

data["script_word_count"] = (
    script_words
)


# Approximate duration.
# 145 words/minute.
estimated_duration = (
    script_words / 145
) * 60


data[
    "estimated_duration_seconds"
] = round(
    estimated_duration
)


# ============================================================
# DURATION VALIDATION
# ============================================================

if script_words < 430:

    print(
        "WARNING: script is shorter than target:",
        script_words,
        "words"
    )

elif script_words > 570:

    print(
        "WARNING: script is longer than target:",
        script_words,
        "words"
    )

else:

    print(
        "Script length OK:",
        script_words,
        "words"
    )


# ============================================================
# SAVE CONTENT PACKAGE
# ============================================================

PACKAGE_FILE.write_text(
    json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)


# ============================================================
# UPDATE AUTOMATION STATE
# ============================================================

topic = clean_text(
    data["topic"]
)

updated_topics = list(
    previous_topics
)

if topic:

    if topic in updated_topics:

        updated_topics.remove(
            topic
        )

    updated_topics.append(
        topic
    )


updated_topics = (
    updated_topics[-100:]
)


new_state = {
    "channel": CHANNEL_NAME,
    "last_topic": topic,
    "last_title": data["title"],
    "last_script_word_count":
        script_words,
    "last_estimated_duration_seconds":
        round(estimated_duration),
    "previous_topics":
        updated_topics
}


STATE_FILE.write_text(
    json.dumps(
        new_state,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)


# ============================================================
# FINAL VERIFICATION
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
    data["topic"]
)

print(
    "Title:",
    data["title"]
)

print(
    "Script words:",
    script_words
)

print(
    "Estimated duration:",
    round(
        estimated_duration
    ),
    "seconds"
)

print(
    "Long scenes:",
    len(
        data["scenes"]
    )
)

print(
    "Short scenes:",
    len(
        data["short_scenes"]
    )
)

print(
    "Hashtags:",
    " ".join(
        data["hashtags"]
    )
)

print(
    "YouTube tags:",
    len(
        data["tags"]
    )
)

print(
    "Script field:",
    "READY"
)

print(
    "long_scenes field:",
    "READY"
)

print(
    "content_package.json:",
    "READY"
)

print(
    "automation_state.json:",
    "READY"
)

print(
    "================================================"
)
