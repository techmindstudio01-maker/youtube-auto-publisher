import json
import os
import re
import time
import math
import random
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone


# ============================================================
# TECHMIND STUDIO — AI CONTENT ENGINE
# STEP 2
# Original tutorial-focused content generation
# ============================================================

PACKAGE_FILE = Path("content_package.json")
STATE_FILE = Path("automation_state.json")

GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY",
    ""
)

NEWS_URL = (
    "https://news.google.com/rss/search?"
    "q=AI%20OR%20artificial%20intelligence"
    "&hl=en-US&gl=US&ceid=US:en"
)

MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash-lite",
]

TARGET_MIN_WORDS = 480
TARGET_MAX_WORDS = 530

SCENE_COUNT = 9


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value):
    if not value:
        return ""

    value = str(value)

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


def strip_code_fences(text):
    text = text.strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.I
    )

    text = re.sub(
        r"^```\s*",
        "",
        text
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    return text.strip()


def parse_json(text):

    text = strip_code_fences(text)

    try:
        return json.loads(text)

    except Exception:
        start = text.find("{")
        end = text.rfind("}")

        if start >= 0 and end > start:

            candidate = text[
                start:end + 1
            ]

            return json.loads(candidate)

        raise


# ============================================================
# NEWS
# ============================================================

def fetch_ai_news():

    print(
        "Fetching fresh AI news..."
    )

    try:

        response = requests.get(
            NEWS_URL,
            timeout=20,
            headers={
                "User-Agent":
                "TechMindStudio/1.0"
            }
        )

        response.raise_for_status()

        root = ET.fromstring(
            response.text
        )

        headlines = []

        for item in root.findall(
            ".//item"
        ):

            title = item.findtext(
                "title"
            )

            if title:

                title = clean_text(
                    title
                )

                if title not in headlines:
                    headlines.append(
                        title
                    )

        print(
            "Found",
            len(headlines),
            "headlines."
        )

        return headlines[:20]

    except Exception as e:

        print(
            "News fetch failed:",
            e
        )

        return []


# ============================================================
# PREVIOUS TOPICS
# ============================================================

def load_previous_topics():

    if not STATE_FILE.exists():
        return []

    try:

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        topics = data.get(
            "previous_topics",
            []
        )

        if isinstance(
            topics,
            list
        ):
            return topics[-30:]

    except Exception:
        pass

    return []


def save_state(
    topic,
    title
):

    state = {}

    if STATE_FILE.exists():

        try:

            with open(
                STATE_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                state = json.load(f)

        except Exception:
            state = {}

    topics = state.get(
        "previous_topics",
        []
    )

    if not isinstance(
        topics,
        list
    ):
        topics = []

    topics.append(
        clean_text(topic)
    )

    topics = topics[-30:]

    state[
        "previous_topics"
    ] = topics

    state[
        "last_title"
    ] = title

    state[
        "last_run"
    ] = datetime.now(
        timezone.utc
    ).isoformat()

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            state,
            f,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# GEMINI
# ============================================================

def call_gemini(
    prompt,
    model
):

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
    )

    response = requests.post(
        url,
        params={
            "key": GEMINI_API_KEY
        },
        json={
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
                "temperature": 0.85,
                "topP": 0.92,
                "maxOutputTokens": 10000
            }
        },
        timeout=90
    )

    print(
        "Gemini HTTP:",
        response.status_code
    )

    if response.status_code != 200:

        print(
            response.text[:1000]
        )

        raise RuntimeError(
            f"Gemini error {response.status_code}"
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
            text += part["text"]

    if not text.strip():

        raise RuntimeError(
            "Gemini returned empty text."
        )

    return text


# ============================================================
# PROMPT
# ============================================================

def build_prompt(
    headlines,
    previous_topics
):

    news_text = "\n".join(
        f"- {x}"
        for x in headlines
    )

    previous_text = "\n".join(
        f"- {x}"
        for x in previous_topics
    )

    return f"""
You are the senior YouTube content strategist,
scriptwriter and visual director for:

TECHMIND STUDIO

Create ONE completely original YouTube tutorial
about AI, YouTube automation, AI tools, or AI-powered
creator workflows.

The video must feel like a premium modern technology
tutorial, not a slideshow.

IMPORTANT CONTENT DIRECTION:

Use a strong "I Built / I Tested / Here's How"
storytelling angle whenever appropriate.

Preferred example:

"I Built a Viral YouTube Channel Using AI —
Here's Exactly How"

The video must teach the viewer something useful.

Do NOT copy another creator's:
- script
- title wording
- thumbnail
- exact scenes
- distinctive visual identity
- dialogue
- jokes

Create original material.

VIDEO LENGTH:

Target:
480–530 spoken words.

The finished narration should normally land around
3:15–3:45.

ABSOLUTE MAXIMUM:
3:50.

STRUCTURE:

1. 0–10 sec:
   powerful curiosity hook

2. Problem:
   explain why the normal approach is difficult

3. Discovery:
   introduce the AI-powered workflow

4. Step-by-step:
   show how to build the channel

5. Practical examples:
   explain actual decisions

6. Results / expected outcome:
   explain what the workflow achieves

7. Final takeaway

8. Natural CTA:
   Like, subscribe and comment

VISUAL DIRECTION:

This is extremely important.

Every scene must be designed for
professional motion graphics.

NO generic stock-photo slideshow.

Visuals should include things like:

- realistic browser UI
- YouTube-style dashboard mockups
- search bars
- typing animations
- AI tool cards
- workflow diagrams
- animated arrows
- progress bars
- charts
- counters
- comparison cards
- highlighted keywords
- thumbnail mockups
- title cards
- channel analytics mockups
- cursor movement
- notification animations
- subscribe animations
- clean technology backgrounds
- cinematic transitions

The visuals must clearly match what the narrator
is saying.

VISUAL TIMING:

A major visual should normally remain on screen
about 6–12 seconds.

NEVER design a scene around one static image
lasting 20–30 seconds.

Create visual changes frequently.

Create exactly 9 major scenes.

Each scene should have a clear purpose.

For every scene provide:

- scene_number
- narration
- visual_query
- visual_type
- on_screen_text
- animation_direction
- key_visuals

visual_type examples:

"browser_ui"
"dashboard"
"motion_graphic"
"animated_chart"
"workflow_diagram"
"comparison_cards"
"thumbnail_mockup"
"youtube_ui"
"cinematic_title"
"cta"

animation_direction must explain
how the renderer should animate the scene.

Example:

"Search bar types the query, results appear,
top result highlights, then camera smoothly
moves toward the selected result."

key_visuals must contain 2–4 concrete visual elements.

TITLE:

Under 100 characters.

Use 1–2 relevant emojis.

Make it curiosity-driven but truthful.

DESCRIPTION:

Write a useful YouTube description.

Include relevant hashtags.

HASHTAGS:

5–8 relevant hashtags.

TAGS:

10–15 YouTube search tags.

CTA:

The final scene should naturally encourage:

LIKE
SHARE
SUBSCRIBE

without sounding desperate.

FRESHNESS:

Here are current AI-related headlines:

{news_text}

Avoid simply repeating a headline.

Previous topics already used:

{previous_text}

Do not make the new topic substantially identical
to previous topics.

OUTPUT:

Return ONLY valid JSON.

Use exactly this structure:

{{
  "topic": "",
  "title": "",
  "hook": "",
  "description": "",
  "hashtags": [],
  "tags": [],
  "script": "",
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "",
      "visual_query": "",
      "visual_type": "",
      "on_screen_text": "",
      "animation_direction": "",
      "key_visuals": []
    }}
  ]
}}

Exactly 9 scenes.

No markdown.
No explanation outside JSON.
"""


# ============================================================
# VALIDATION
# ============================================================

def normalize_output(data):

    if not isinstance(
        data,
        dict
    ):
        raise RuntimeError(
            "Gemini output is not an object."
        )

    title = clean_text(
        data.get(
            "title",
            ""
        )
    )

    topic = clean_text(
        data.get(
            "topic",
            ""
        )
    )

    hook = clean_text(
        data.get(
            "hook",
            ""
        )
    )

    description = clean_text(
        data.get(
            "description",
            ""
        )
    )

    script = clean_text(
        data.get(
            "script",
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

    scenes = data.get(
        "scenes",
        []
    )

    if not isinstance(
        hashtags,
        list
    ):
        hashtags = []

    if not isinstance(
        tags,
        list
    ):
        tags = []

    if not isinstance(
        scenes,
        list
    ):
        scenes = []

    hashtags = [
        clean_text(x)
        for x in hashtags
        if clean_text(x)
    ]

    tags = [
        clean_text(x)
        for x in tags
        if clean_text(x)
    ]

    # Ensure hashtag format
    fixed_hashtags = []

    for tag in hashtags:

        if not tag.startswith("#"):
            tag = "#" + tag

        fixed_hashtags.append(
            tag.replace(
                " ",
                ""
            )
        )

    hashtags = fixed_hashtags[:8]

    if len(hashtags) < 5:

        defaults = [
            "#AI",
            "#ArtificialIntelligence",
            "#YouTubeAutomation",
            "#AITools",
            "#TechMindStudio"
        ]

        for item in defaults:

            if item not in hashtags:
                hashtags.append(item)

            if len(hashtags) >= 5:
                break

    tags = tags[:15]

    if len(tags) < 10:

        defaults = [
            "AI tools",
            "AI YouTube",
            "YouTube automation",
            "faceless YouTube",
            "AI content creation",
            "AI video",
            "YouTube growth",
            "AI creator",
            "YouTube channel",
            "TechMind Studio"
        ]

        for item in defaults:

            if item not in tags:
                tags.append(item)

            if len(tags) >= 10:
                break

    normalized_scenes = []

    for index in range(
        SCENE_COUNT
    ):

        source = (
            scenes[index]
            if index < len(scenes)
            and isinstance(
                scenes[index],
                dict
            )
            else {}
        )

        narration = clean_text(
            source.get(
                "narration",
                ""
            )
        )

        visual_query = clean_text(
            source.get(
                "visual_query",
                ""
            )
        )

        visual_type = clean_text(
            source.get(
                "visual_type",
                "motion_graphic"
            )
        )

        on_screen_text = clean_text(
            source.get(
                "on_screen_text",
                ""
            )
        )

        animation_direction = clean_text(
            source.get(
                "animation_direction",
                ""
            )
        )

        key_visuals = source.get(
            "key_visuals",
            []
        )

        if not isinstance(
            key_visuals,
            list
        ):
            key_visuals = []

        key_visuals = [
            clean_text(x)
            for x in key_visuals
            if clean_text(x)
        ]

        normalized_scenes.append(
            {
                "scene_number":
                    index + 1,
                "narration":
                    narration,
                "visual_query":
                    visual_query,
                "visual_type":
                    visual_type,
                "on_screen_text":
                    on_screen_text,
                "animation_direction":
                    animation_direction,
                "key_visuals":
                    key_visuals[:4]
            }
        )

    # --------------------------------------------------------
    # Fallbacks
    # --------------------------------------------------------

    fallback_narrations = [
        "The first step is finding a niche where people already want answers, instead of creating content blindly.",
        "Next, use AI to turn audience demand into specific video ideas with a clear problem and a strong curiosity gap.",
        "Then build a script around a powerful opening, useful information, examples, and a clear payoff for the viewer.",
        "AI tools can help create natural narration, but the story and information still need to be useful and original.",
        "The visuals should explain the idea through interfaces, diagrams, charts, and animated callouts instead of random stock images.",
        "A strong title and thumbnail work together to create curiosity while accurately representing what the video delivers.",
        "Once the video is ready, the workflow can prepare the description, hashtags, tags, thumbnail, and upload package automatically.",
        "The goal is not to publish more low-quality videos, but to build a repeatable system that produces genuinely useful content.",
        "Finally, turn the strongest ideas into a consistent publishing system and keep improving based on what viewers actually respond to."
    ]

    fallback_types = [
        "browser_ui",
        "workflow_diagram",
        "motion_graphic",
        "dashboard",
        "animated_chart",
        "thumbnail_mockup",
        "youtube_ui",
        "comparison_cards",
        "cta"
    ]

    for index, scene in enumerate(
        normalized_scenes
    ):

        if not scene["narration"]:
            scene["narration"] = (
                fallback_narrations[index]
            )

        if not scene["visual_query"]:

            scene["visual_query"] = (
                "AI YouTube creator "
                "workflow technology "
                "interface"
            )

        if not scene["visual_type"]:

            scene["visual_type"] = (
                fallback_types[index]
            )

        if not scene["on_screen_text"]:

            scene["on_screen_text"] = (
                [
                    "FIND THE RIGHT NICHE",
                    "FIND VIDEO IDEAS",
                    "BUILD THE HOOK",
                    "WRITE THE SCRIPT",
                    "CREATE THE VISUALS",
                    "DESIGN THE THUMBNAIL",
                    "PREPARE THE UPLOAD",
                    "AUTOMATE THE WORKFLOW",
                    "BUILD THE SYSTEM"
                ][index]
            )

        if not scene[
            "animation_direction"
        ]:

            scene[
                "animation_direction"
            ] = (
                "Use smooth cinematic motion, "
                "progressive reveals, subtle "
                "camera movement and clear "
                "highlight animations."
            )

        if not scene[
            "key_visuals"
        ]:

            scene[
                "key_visuals"
            ] = [
                "clean technology interface",
                "animated highlight",
                "relevant diagram"
            ]

    if not title:

        title = (
            "I Built a Viral YouTube "
            "Channel Using AI 🤖🚀"
        )

    if not topic:

        topic = (
            "Building a YouTube channel "
            "with AI"
        )

    if not hook:

        hook = (
            "What if AI could help build "
            "almost the entire YouTube "
            "workflow?"
        )

    if not description:

        description = (
            "Learn how to build a modern "
            "AI-powered YouTube workflow "
            "from niche research to publishing. "
            "This TechMind Studio tutorial "
            "breaks down the process step by step."
        )

    return {
        "topic": topic,
        "title": title[:100],
        "hook": hook,
        "description": description,
        "hashtags": hashtags,
        "tags": tags,
        "script": script,
        "scenes": normalized_scenes
    }


# ============================================================
# MAIN GENERATION
# ============================================================

if not GEMINI_API_KEY:

    raise RuntimeError(
        "GEMINI_API_KEY secret is missing."
    )


headlines = fetch_ai_news()

previous_topics = (
    load_previous_topics()
)

print(
    "Previous topics:",
    len(previous_topics)
)

prompt = build_prompt(
    headlines,
    previous_topics
)


result = None
last_error = None

for attempt in range(1, 6):

    model = MODELS[
        (attempt - 1)
        % len(MODELS)
    ]

    print(
        f"\nGemini attempt "
        f"{attempt}/5..."
    )

    print(
        "Model:",
        model
    )

    try:

        raw = call_gemini(
            prompt,
            model
        )

        parsed = parse_json(
            raw
        )

        result = normalize_output(
            parsed
        )

        break

    except Exception as e:

        last_error = e

        print(
            "Generation failed:",
            e
        )

        if attempt < 5:

            time.sleep(
                3 * attempt
            )


if result is None:

    raise RuntimeError(
        "All Gemini attempts failed: "
        + str(last_error)
    )


# ============================================================
# SCRIPT VALIDATION
# ============================================================

count = word_count(
    result["script"]
)

print(
    "\n=========================================="
)

print(
    "CONTENT GENERATED"
)

print(
    "=========================================="
)

print(
    "Title:",
    result["title"]
)

print(
    "Topic:",
    result["topic"]
)

print(
    "Script words:",
    count
)

print(
    "Scenes:",
    len(result["scenes"])
)

print(
    "Hashtags:",
    ", ".join(
        result["hashtags"]
    )
)

print(
    "Tags:",
    ", ".join(
        result["tags"]
    )
)


# Do not reject slightly short/long output.
# Keep the pipeline resilient.
if count < 420:

    print(
        "WARNING: script is shorter "
        "than target."
    )

if count > 600:

    print(
        "WARNING: script is longer "
        "than target."
    )


# ============================================================
# ESTIMATE DURATION
# ============================================================

WORDS_PER_MINUTE = 145

estimated_seconds = (
    count
    / WORDS_PER_MINUTE
    * 60
)

estimated_seconds = min(
    estimated_seconds,
    230
)

result[
    "script_word_count"
] = count

result[
    "estimated_duration_seconds"
] = round(
    estimated_seconds,
    2
)

result[
    "generated_at"
] = datetime.now(
    timezone.utc
).isoformat()

result[
    "brand"
] = "TechMind Studio"

result[
    "format"
] = "tutorial"

result[
    "visual_style"
] = (
    "original 4K motion graphics "
    "technology tutorial"
)


# ============================================================
# SAVE
# ============================================================

with open(
    PACKAGE_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        result,
        f,
        indent=2,
        ensure_ascii=False
    )


save_state(
    result["topic"],
    result["title"]
)


print(
    "\n=========================================="
)

print(
    "CONTENT PACKAGE SAVED"
)

print(
    "=========================================="
)

print(
    "File:",
    PACKAGE_FILE
)

print(
    "Estimated duration:",
    round(
        estimated_seconds,
        1
    ),
    "seconds"
)

print(
    "=========================================="
)

print(
    "TECHMIND STUDIO CONTENT READY"
)

print(
    "=========================================="
)
