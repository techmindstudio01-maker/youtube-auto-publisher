import os
import json
import re
import time
import random
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


# ============================================================
# TechMind Studio - AI Automation Engine
# ============================================================

print("=" * 60)
print("TechMind Studio - Automation Engine")
print("=" * 60)


# ============================================================
# CONFIG
# ============================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Primary + fallback models
MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash-lite",
]

OUTPUT_FILE = "content_package.json"
STATE_FILE = "automation_state.json"

MAX_MODEL_ATTEMPTS = 3


# ============================================================
# STATE
# ============================================================

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)

            if not isinstance(state, dict):
                raise ValueError("Invalid state format")

            state.setdefault("generated_topics", [])
            state.setdefault("generated_titles", [])
            state.setdefault("last_run", None)
            state.setdefault("run_count", 0)

            return state

        except Exception as e:
            print(f"Warning: Could not load state: {e}")

    return {
        "generated_topics": [],
        "generated_titles": [],
        "last_run": None,
        "run_count": 0,
    }


def save_state(state):
    temp_file = STATE_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    os.replace(temp_file, STATE_FILE)


# ============================================================
# NEWS
# ============================================================

def get_news():
    print("Fetching fresh AI news...")

    rss_url = (
        "https://news.google.com/rss/search?"
        "q=AI%20OR%20artificial%20intelligence%20OR%20technology"
        "&hl=en-US&gl=US&ceid=US:en"
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(
            rss_url,
            headers=headers,
            timeout=30
        )

        response.raise_for_status()

        root = ET.fromstring(response.content)

        headlines = []

        for item in root.findall(".//item"):
            title = item.findtext("title")

            if title:
                title = title.strip()

                if title and title not in headlines:
                    headlines.append(title)

            if len(headlines) >= 20:
                break

        print(f"Found {len(headlines)} headlines.")

        return headlines

    except Exception as e:
        print(f"News fetch failed: {e}")

        return [
            "Artificial intelligence continues to transform software and business",
            "AI assistants are becoming more capable",
            "Companies are rapidly adopting generative AI",
            "AI automation is changing online work",
            "New AI tools are launching across technology",
        ]


# ============================================================
# JSON CLEANER
# ============================================================

def clean_json(text):
    text = text.strip()

    # Remove markdown code fences
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # Find JSON object if model added extra text
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    return text.strip()


# ============================================================
# GEMINI REQUEST
# ============================================================

def call_gemini(model, prompt):
    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
    )

    params = {
        "key": GEMINI_API_KEY
    }

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": 4000,
            "responseMimeType": "application/json"
        }
    }

    response = requests.post(
        url,
        params=params,
        json=payload,
        timeout=90
    )

    if response.status_code != 200:
        print(
            f"Gemini HTTP error: {response.status_code} "
            f"using {model}"
        )

        try:
            error_data = response.json()
            print(
                "Gemini error:",
                json.dumps(error_data, ensure_ascii=False)[:1000]
            )
        except Exception:
            print(response.text[:1000])

        return None

    data = response.json()

    try:
        candidates = data.get("candidates", [])

        if not candidates:
            print("Gemini returned no candidates.")
            return None

        parts = candidates[0].get("content", {}).get("parts", [])

        text_parts = []

        for part in parts:
            if "text" in part:
                text_parts.append(part["text"])

        result = "".join(text_parts).strip()

        if not result:
            print("Gemini returned empty text.")
            return None

        return result

    except Exception as e:
        print(f"Could not parse Gemini response: {e}")
        return None


# ============================================================
# CONTENT GENERATION
# ============================================================

def generate_content(headlines, state):

    print("Generating a NEW topic...")

    previous_topics = state.get("generated_topics", [])
    previous_titles = state.get("generated_titles", [])

    headlines_text = "\n".join(
        f"- {headline}"
        for headline in headlines
    )

    previous_topics_text = "\n".join(
        f"- {topic}"
        for topic in previous_topics[-30:]
    )

    previous_titles_text = "\n".join(
        f"- {title}"
        for title in previous_titles[-30:]
    )

    prompt = f"""
You are the senior content strategist for a YouTube channel called
"TechMind Studio".

Create ONE completely fresh YouTube video idea based on current AI
and technology news.

The content must be suitable for an original 4-5 minute YouTube video.

IMPORTANT:
- Do NOT copy any article.
- Do NOT create a generic topic.
- Pick a specific, interesting AI/technology angle.
- Make the topic attractive for viewers.
- The title should have a strong curiosity hook.
- Add 1-2 relevant emojis to the title.
- The title must NOT be identical or nearly identical to previous titles.
- The topic must NOT repeat previous topics.
- Description should be useful and YouTube-ready.
- Include relevant hashtags.
- Include YouTube search tags.
- Create a strong opening hook.
- Create a short URL-safe slug.
- Return ONLY valid JSON.
- No markdown.
- No explanation outside JSON.

CURRENT NEWS HEADLINES:
{headlines_text}

PREVIOUS TOPICS:
{previous_topics_text}

PREVIOUS TITLES:
{previous_titles_text}

Return exactly this structure:

{{
  "topic": "specific video topic",
  "title": "attention-grabbing YouTube title with relevant emoji",
  "description": "YouTube-ready description",
  "hashtags": [
    "#AI",
    "#ArtificialIntelligence",
    "#Technology"
  ],
  "tags": [
    "AI",
    "artificial intelligence",
    "AI tools",
    "technology"
  ],
  "hook": "strong first 10-15 second hook",
  "slug": "short-url-safe-slug"
}}
"""

    # --------------------------------------------------------
    # Try every model with exponential backoff
    # --------------------------------------------------------

    for model in MODELS:

        print()
        print(f"Trying Gemini model: {model}")

        for attempt in range(1, MAX_MODEL_ATTEMPTS + 1):

            print(
                f"Attempt {attempt}/{MAX_MODEL_ATTEMPTS} "
                f"using {model}..."
            )

            result = call_gemini(
                model=model,
                prompt=prompt
            )

            if result:

                try:
                    package = json.loads(
                        clean_json(result)
                    )

                    required_fields = [
                        "topic",
                        "title",
                        "description",
                        "hashtags",
                        "tags",
                        "hook",
                        "slug",
                    ]

                    missing = [
                        field
                        for field in required_fields
                        if field not in package
                    ]

                    if missing:
                        print(
                            "Gemini JSON missing fields:",
                            missing
                        )
                    else:

                        topic = str(
                            package["topic"]
                        ).strip()

                        title = str(
                            package["title"]
                        ).strip()

                        # Duplicate protection
                        duplicate_topic = any(
                            topic.lower() == str(old).lower()
                            for old in previous_topics
                        )

                        duplicate_title = any(
                            title.lower() == str(old).lower()
                            for old in previous_titles
                        )

                        if duplicate_topic:
                            print(
                                "Duplicate topic detected. "
                                "Requesting another idea."
                            )
                            prompt += (
                                "\nIMPORTANT: Your previous answer "
                                "was a duplicate. Generate a "
                                "completely different topic."
                            )
                            continue

                        if duplicate_title:
                            print(
                                "Duplicate title detected. "
                                "Requesting another title."
                            )
                            prompt += (
                                "\nIMPORTANT: Your previous answer "
                                "used a duplicate title. Generate "
                                "a completely different title."
                            )
                            continue

                        # Ensure lists
                        if not isinstance(
                            package["hashtags"],
                            list
                        ):
                            package["hashtags"] = []

                        if not isinstance(
                            package["tags"],
                            list
                        ):
                            package["tags"] = []

                        print()
                        print("CONTENT GENERATED SUCCESSFULLY")
                        print("--------------------------------")
                        print("Topic:", topic)
                        print("Title:", title)
                        print("Hook:", package["hook"])
                        print(
                            "Hashtags:",
                            ", ".join(
                                map(
                                    str,
                                    package["hashtags"]
                                )
                            )
                        )
                        print(
                            "Tags:",
                            ", ".join(
                                map(
                                    str,
                                    package["tags"]
                                )
                            )
                        )

                        return package

                except json.JSONDecodeError as e:
                    print(
                        "Invalid JSON returned by Gemini:",
                        e
                    )

            # ------------------------------------------------
            # Exponential backoff
            # ------------------------------------------------

            if attempt < MAX_MODEL_ATTEMPTS:

                wait_seconds = min(
                    60,
                    (2 ** (attempt - 1)) * 5
                    + random.uniform(0, 3)
                )

                print(
                    f"Waiting {wait_seconds:.1f}s "
                    "before retry..."
                )

                time.sleep(wait_seconds)

        print()
        print(
            f"Model {model} failed after "
            f"{MAX_MODEL_ATTEMPTS} attempts."
        )

        print("Switching to fallback model...")

    raise RuntimeError(
        "All Gemini models failed. "
        "No content package could be generated."
    )


# ============================================================
# SAVE CONTENT PACKAGE
# ============================================================

def save_package(package, state):

    now = datetime.now(
        timezone.utc
    ).isoformat()

    package["channel"] = "TechMind Studio"
    package["generated_at"] = now

    # Clean hashtag values
    cleaned_hashtags = []

    for hashtag in package.get("hashtags", []):

        hashtag = str(hashtag).strip()

        if hashtag and not hashtag.startswith("#"):
            hashtag = "#" + hashtag

        if hashtag:
            cleaned_hashtags.append(hashtag)

    package["hashtags"] = cleaned_hashtags

    # Clean tags
    package["tags"] = [
        str(tag).strip()
        for tag in package.get("tags", [])
        if str(tag).strip()
    ]

    # Save package
    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            package,
            f,
            indent=2,
            ensure_ascii=False
        )

    # Update state
    state["generated_topics"].append(
        package["topic"]
    )

    state["generated_titles"].append(
        package["title"]
    )

    # Keep state manageable
    state["generated_topics"] = (
        state["generated_topics"][-50:]
    )

    state["generated_titles"] = (
        state["generated_titles"][-50:]
    )

    state["last_run"] = now

    state["run_count"] = (
        int(state.get("run_count", 0)) + 1
    )

    save_state(state)

    print()
    print("=" * 60)
    print("CONTENT PACKAGE SAVED")
    print("=" * 60)

    print(f"File: {OUTPUT_FILE}")
    print(f"State: {STATE_FILE}")
    print(f"Run count: {state['run_count']}")
    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

def main():

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY secret is missing."
        )

    state = load_state()

    print(
        "Previous topics:",
        len(state.get("generated_topics", []))
    )

    headlines = get_news()

    package = generate_content(
        headlines=headlines,
        state=state
    )

    save_package(
        package=package,
        state=state
    )

    print()
    print("Automation engine completed successfully.")


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
