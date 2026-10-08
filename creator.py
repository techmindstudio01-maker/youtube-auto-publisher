import os
import json
import re
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# ============================================================
# TechMind Studio - AI Content Creator
# TARGET: 3:15 - 3:45 LONG VIDEO
# ============================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CONTENT_FILE = "content_package.json"
STATE_FILE = "automation_state.json"

TARGET_MIN_WORDS = 480
TARGET_MAX_WORDS = 530
TARGET_SCENES = 9

MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash-lite",
]

NEWS_URL = (
    "https://news.google.com/rss/search"
    "?q=AI%20technology%20artificial%20intelligence"
    "&hl=en-IN&gl=IN&ceid=IN:en"
)


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"used_topics": []}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return {"used_topics": []}

        data.setdefault("used_topics", [])
        return data

    except Exception:
        return {"used_topics": []}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_ai_news():
    print("Fetching fresh AI news...")

    try:
        response = requests.get(
            NEWS_URL,
            timeout=30,
            headers={
                "User-Agent": "TechMindStudio-Automation/1.0"
            },
        )

        response.raise_for_status()

        root = ET.fromstring(response.text)

        headlines = []

        for item in root.findall(".//item"):
            title = item.findtext("title")

            if title:
                title = clean_text(title)

                if title and title not in headlines:
                    headlines.append(title)

        print(f"Found {len(headlines)} headlines.")

        return headlines[:20]

    except Exception as e:
        print("News fetch failed:", e)
        return []


def call_gemini(prompt):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing.")

    for model in MODELS:
        print(f"Trying Gemini model: {model}")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{model}:generateContent"
            f"?key={GEMINI_API_KEY}"
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
                "temperature": 0.85,
                "maxOutputTokens": 9000
            }
        }

        for attempt in range(1, 4):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=120
                )

                print(
                    f"Gemini HTTP {response.status_code} "
                    f"(attempt {attempt}/3)"
                )

                if response.status_code == 200:
                    data = response.json()

                    candidates = data.get("candidates", [])

                    if not candidates:
                        raise RuntimeError(
                            "Gemini returned no candidates."
                        )

                    parts = (
                        candidates[0]
                        .get("content", {})
                        .get("parts", [])
                    )

                    text_parts = []

                    for part in parts:
                        if "text" in part:
                            text_parts.append(part["text"])

                    result = "\n".join(text_parts).strip()

                    if result:
                        return result

                    raise RuntimeError(
                        "Gemini returned empty text."
                    )

                if response.status_code in (429, 500, 502, 503, 504):
                    time.sleep(5 * attempt)
                    continue

                print(response.text[:1000])

                break

            except Exception as e:
                print("Gemini error:", e)

                if attempt < 3:
                    time.sleep(5)

    raise RuntimeError(
        "All Gemini models failed."
    )


def extract_json(text):
    text = text.strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
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

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(
        r"\{.*\}",
        text,
        flags=re.DOTALL
    )

    if not match:
        raise RuntimeError(
            "Could not find JSON in Gemini response."
        )

    return json.loads(match.group(0))


def word_count(text):
    return len(
        re.findall(
            r"\b[\w'-]+\b",
            text or ""
        )
    )


def normalize_package(data):
    title = clean_text(data.get("title", ""))
    description = clean_text(data.get("description", ""))
    hook = clean_text(data.get("hook", ""))
    script = clean_text(data.get("script", ""))

    hashtags = data.get("hashtags", [])
    tags = data.get("tags", [])
    scenes = data.get("scenes", [])

    if not isinstance(hashtags, list):
        hashtags = []

    if not isinstance(tags, list):
        tags = []

    if not isinstance(scenes, list):
        scenes = []

    normalized_scenes = []

    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            continue

        narration = clean_text(
            scene.get("narration", "")
        )

        if not narration:
            continue

        normalized_scenes.append(
            {
                "scene_number": index,
                "heading": clean_text(
                    scene.get(
                        "heading",
                        f"Scene {index}"
                    )
                ),
                "narration": narration,
                "visual_query": clean_text(
                    scene.get(
                        "visual_query",
                        title
                    )
                ),
                "visual_type": clean_text(
                    scene.get(
                        "visual_type",
                        "photo"
                    )
                ),
                "on_screen_text": clean_text(
                    scene.get(
                        "on_screen_text",
                        ""
                    )
                ),
            }
        )

    return {
        "topic": clean_text(
            data.get("topic", "")
        ),
        "title": title,
        "description": description,
        "hashtags": hashtags,
        "tags": tags,
        "hook": hook,
        "slug": clean_text(
            data.get("slug", "")
        ),
        "script": script,
        "scenes": normalized_scenes,
    }


def main():

    print("=" * 60)
    print("TechMind Studio - Automation Engine")
    print("TARGET VIDEO LENGTH: 3:15 - 3:45")
    print("=" * 60)

    state = load_state()

    used_topics = [
        clean_text(x).lower()
        for x in state.get("used_topics", [])
    ]

    print(
        f"Previous topics: {len(used_topics)}"
    )

    headlines = fetch_ai_news()

    if not headlines:
        headlines = [
            "Latest artificial intelligence developments",
            "New AI tools changing productivity",
            "The latest AI technology people should know",
        ]

    available = [
        h for h in headlines
        if clean_text(h).lower() not in used_topics
    ]

    if not available:
        available = headlines

    news_text = "\n".join(
        f"- {h}"
        for h in available[:15]
    )

    prompt = f"""
You are the senior content producer for a YouTube channel called
"TechMind Studio".

Create ONE original, highly engaging AI/technology YouTube video.

The final narration must be suitable for approximately
3 minutes 15 seconds to 3 minutes 45 seconds.

IMPORTANT:
- Total script narration: 480-530 words.
- Do NOT write 650+ words.
- Create exactly 9 scenes.
- Each scene should contain useful narration.
- The video must feel like a professional YouTube tutorial/explainer.
- Strong hook in the first 10 seconds.
- No filler.
- No repeated points.
- Natural spoken English.
- Explain the topic clearly.
- Use practical examples.
- End with a short CTA for TechMind Studio.

Fresh news headlines:
{news_text}

Return ONLY valid JSON.

Required structure:

{{
  "topic": "...",
  "title": "...",
  "description": "...",
  "hashtags": ["#AI", "#ArtificialIntelligence"],
  "tags": ["AI", "artificial intelligence"],
  "hook": "...",
  "slug": "...",
  "script": "...",
  "scenes": [
    {{
      "scene_number": 1,
      "heading": "...",
      "narration": "...",
      "visual_query": "...",
      "visual_type": "photo",
      "on_screen_text": "..."
    }}
  ]
}}

TITLE RULES:
- Attractive YouTube title.
- Include 1-2 relevant emojis such as 🤖, 🔥, 🚀, 💡.
- Do not use fake claims.
- Keep it under 100 characters.

DESCRIPTION:
- Write a useful YouTube description.
- Include a natural CTA.
- Do not put hashtags in the description field.

HASHTAGS:
- Provide 5-8 relevant hashtags.
- Every hashtag must begin with #.

TAGS:
- Provide 10-15 relevant YouTube search tags.

SCRIPT:
- 480-530 words total.
- Strong opening.
- Natural narration.
- No section labels inside narration.

SCENES:
- Exactly 9 scenes.
- The combined narration should match the script.
- Every scene needs a distinct visual_query.
- Visual queries should be easy to search on Wikimedia Commons.
- Avoid copyrighted logos where possible.
"""

    print("Generating a NEW topic...")

    raw = call_gemini(prompt)

    data = extract_json(raw)

    package = normalize_package(data)

    script_words = word_count(
        package["script"]
    )

    scene_words = sum(
        word_count(
            scene["narration"]
        )
        for scene in package["scenes"]
    )

    print("Generated title:")
    print(package["title"])

    print(
        f"Script words: {script_words}"
    )

    print(
        f"Scene count: {len(package['scenes'])}"
    )

    # If Gemini produced no scenes, create a simple
    # fallback scene list from the script.
    if len(package["scenes"]) == 0:

        print(
            "WARNING: Gemini returned no scenes."
        )

        words = package["script"].split()

        if words:
            chunk_size = max(
                1,
                math.ceil(
                    len(words) / TARGET_SCENES
                )
            )

            generated = []

            for i in range(
                0,
                len(words),
                chunk_size
            ):
                chunk = " ".join(
                    words[i:i + chunk_size]
                )

                scene_number = len(generated) + 1

                generated.append(
                    {
                        "scene_number": scene_number,
                        "heading": f"Scene {scene_number}",
                        "narration": chunk,
                        "visual_query": package["topic"],
                        "visual_type": "photo",
                        "on_screen_text": "",
                    }
                )

            package["scenes"] = generated

    package["script_word_count"] = word_count(
        package["script"]
    )

    package["scene_word_count"] = scene_words

    package["estimated_duration_seconds"] = round(
        package["script_word_count"] / 145 * 60
    )

    package["generated_at"] = datetime.now(
        timezone.utc
    ).isoformat()

    # Save used topic.
    topic = package.get("topic", "")

    if topic:
        state.setdefault(
            "used_topics",
            []
        )

        state["used_topics"].append(topic)

        # Keep state manageable.
        state["used_topics"] = (
            state["used_topics"][-100:]
        )

    save_state(state)

    with open(
        CONTENT_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            package,
            f,
            indent=2,
            ensure_ascii=False
        )

    print("=" * 60)
    print("CONTENT PACKAGE CREATED")
    print("Title:", package["title"])
    print(
        "Words:",
        package["script_word_count"]
    )
    print(
        "Scenes:",
        len(package["scenes"])
    )
    print(
        "Estimated duration:",
        package["estimated_duration_seconds"],
        "seconds"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
