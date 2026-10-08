import os
import json
import re
import time
import requests
from datetime import datetime, timezone

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = "gemini-3.8-flash"

OUTPUT_FILE = "content_package.json"
STATE_FILE = "automation_state.json"


def get_news():
    url = "https://news.google.com/rss/search"

    params = {
        "q": "artificial intelligence AI technology",
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=20
        )
        response.raise_for_status()

        items = re.findall(
            r"<item>(.*?)</item>",
            response.text,
            re.S
        )

        headlines = []

        for item in items[:20]:
            match = re.search(
                r"<title>(.*?)</title>",
                item,
                re.S
            )

            if match:
                title = re.sub(
                    r"<.*?>",
                    "",
                    match.group(1)
                )

                title = (
                    title
                    .replace("&amp;", "&")
                    .replace("&quot;", '"')
                    .strip()
                )

                headlines.append(title)

        return headlines

    except Exception as e:
        print("News fetch warning:", e)
        return []


def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "generated_topics": [],
            "generated_titles": [],
            "last_run": None,
            "run_count": 0
        }

    try:
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            return json.load(file)

    except Exception:
        return {
            "generated_topics": [],
            "generated_titles": [],
            "last_run": None,
            "run_count": 0
        }


def save_state(state):
    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            state,
            file,
            indent=2,
            ensure_ascii=False
        )


def clean_json(text):
    text = text.strip()

    text = re.sub(
        r"^```json",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^```",
        "",
        text
    )

    text = re.sub(
        r"```$",
        "",
        text
    )

    return text.strip()


def generate_content(headlines, state):
    today = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    recent_headlines = "\n".join(
        f"- {item}"
        for item in headlines[:15]
    )

    previous_topics = "\n".join(
        f"- {item}"
        for item in state.get(
            "generated_topics",
            []
        )[-20:]
    )

    previous_titles = "\n".join(
        f"- {item}"
        for item in state.get(
            "generated_titles",
            []
        )[-20:]
    )

    prompt = f"""
You are the daily content engine for the YouTube channel
"TechMind Studio".

Date:
{today}

Create ONE original AI/technology YouTube content package.

IMPORTANT:
Do not repeat any previous topic or title.
Choose a genuinely different angle.

Previous topics:
{previous_topics or "None"}

Previous titles:
{previous_titles or "None"}

Fresh AI/technology headlines:
{recent_headlines or "No headlines available"}

Requirements:

- Choose ONE useful and interesting AI/technology topic.
- Make it suitable for a YouTube audience.
- Create a strong curiosity-driven title.
- Add 1 or 2 relevant emojis to the title.
- Create a natural description.
- Include 5-8 relevant hashtags.
- Create 8-15 YouTube tags.
- Create a strong opening hook.
- Create a short filename-safe slug.
- Use "TechMind Studio" as the channel name.
- Do not invent statistics.
- Do not copy article wording.
- Do not repeat previous topics.
- Keep the content original.

Return ONLY valid JSON:

{{
  "topic": "topic",
  "title": "title with emoji",
  "description": "description",
  "hashtags": [
    "#AI",
    "#Technology"
  ],
  "tags": [
    "AI",
    "artificial intelligence"
  ],
  "hook": "strong opening hook",
  "slug": "short-topic-slug"
}}
"""

    url = (
        f"https://generativelanguage.googleapis.com/"
        f"v1beta/models/{MODEL}:generateContent"
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
            "temperature": 0.8,
            "maxOutputTokens": 3000
        }
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY
    }

    for attempt in range(1, 6):

        print(
            f"Gemini attempt {attempt}/5..."
        )

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=90
            )

            if response.status_code != 200:
                print(
                    "Gemini HTTP error:",
                    response.status_code
                )

                time.sleep(attempt * 5)
                continue

            data = response.json()

            text = (
                data["candidates"][0]
                ["content"]["parts"][0]["text"]
            )

            package = json.loads(
                clean_json(text)
            )

            required_fields = [
                "topic",
                "title",
                "description",
                "hashtags",
                "tags",
                "hook",
                "slug"
            ]

            for field in required_fields:
                if field not in package:
                    raise ValueError(
                        f"Missing field: {field}"
                    )

            old_topics = {
                x.lower().strip()
                for x in state.get(
                    "generated_topics",
                    []
                )
            }

            old_titles = {
                x.lower().strip()
                for x in state.get(
                    "generated_titles",
                    []
                )
            }

            topic = package["topic"].lower().strip()
            title = package["title"].lower().strip()

            if topic in old_topics:
                print(
                    "Duplicate topic detected."
                )
                time.sleep(2)
                continue

            if title in old_titles:
                print(
                    "Duplicate title detected."
                )
                time.sleep(2)
                continue

            return package

        except Exception as error:
            print(
                "Generation error:",
                error
            )

            if attempt < 5:
                time.sleep(attempt * 5)

    raise RuntimeError(
        "Unable to generate a new content package "
        "after 5 attempts."
    )


def save_package(package, state):
    now = datetime.now(
        timezone.utc
    ).isoformat()

    package["channel"] = "TechMind Studio"
    package["generated_at"] = now

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            package,
            file,
            indent=2,
            ensure_ascii=False
        )

    state.setdefault(
        "generated_topics",
        []
    ).append(
        package["topic"]
    )

    state.setdefault(
        "generated_titles",
        []
    ).append(
        package["title"]
    )

    state["generated_topics"] = (
        state["generated_topics"][-50:]
    )

    state["generated_titles"] = (
        state["generated_titles"][-50:]
    )

    state["last_run"] = now

    state["run_count"] = (
        state.get("run_count", 0) + 1
    )

    save_state(state)

    print()
    print("=" * 60)
    print("NEW CONTENT PACKAGE CREATED")
    print("=" * 60)
    print("Run number:", state["run_count"])
    print("Topic:", package["topic"])
    print("Title:", package["title"])
    print("Hook:", package["hook"])
    print(
        "Hashtags:",
        ", ".join(package["hashtags"])
    )
    print(
        "Tags:",
        ", ".join(package["tags"])
    )
    print("Saved:", OUTPUT_FILE)
    print("State:", STATE_FILE)
    print("=" * 60)


def main():

    print("=" * 60)
    print("TechMind Studio - Automation Engine")
    print("=" * 60)

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY secret is missing."
        )

    state = load_state()

    print(
        "Previous topics:",
        len(
            state.get(
                "generated_topics",
                []
            )
        )
    )

    print("Fetching fresh AI news...")

    headlines = get_news()

    print(
        f"Found {len(headlines)} headlines."
    )

    print(
        "Generating a NEW topic..."
    )

    package = generate_content(
        headlines,
        state
    )

    save_package(
        package,
        state
    )

    print()
    print(
        "Automation engine completed successfully."
    )
    print(
        "Video generation remains disabled."
    )


if __name__ == "__main__":
    main()
