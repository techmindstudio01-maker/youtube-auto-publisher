import os
import json
import re
import time
import requests
from datetime import datetime, timezone


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = "gemini-3.8-flash"

OUTPUT_FILE = "content_package.json"


def get_news():
    """Get fresh AI-related headlines from Google News RSS."""
    url = "https://news.google.com/rss/search"
    params = {
        "q": "artificial intelligence AI technology",
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }

    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()

        items = re.findall(r"<item>(.*?)</item>", r.text, re.S)

        headlines = []

        for item in items[:20]:
            title = re.search(r"<title>(.*?)</title>", item, re.S)
            if title:
                clean = re.sub(r"<.*?>", "", title.group(1))
                clean = clean.replace("&amp;", "&")
                headlines.append(clean.strip())

        return headlines

    except Exception as e:
        print("News fetch warning:", e)
        return []


def generate_content(headlines):
    """Generate the daily TechMind Studio content package."""

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    news_text = "\n".join(
        f"- {headline}" for headline in headlines[:15]
    )

    prompt = f"""
You are the content automation engine for a YouTube channel called
"TechMind Studio".

Today's date: {today}

Create ONE original AI/technology video content package.

Use the recent headlines below as inspiration, but do NOT copy titles,
sentences, scripts, or copyrighted wording.

Recent headlines:
{news_text}

Requirements:

1. Pick ONE strong, useful AI/technology topic.
2. Make the title attractive and curiosity-driven.
3. Include 1-2 relevant emojis in the title.
4. Create a natural YouTube description.
5. Include 5-8 relevant hashtags in the description.
6. Create 8-15 YouTube tags.
7. Create a strong 1-2 sentence hook.
8. Create a short topic slug for filename use.
9. The channel name must be "TechMind Studio".
10. Do not claim fake statistics or fake breaking news.
11. Do not copy any source wording.

Return ONLY valid JSON in exactly this structure:

{{
  "topic": "topic",
  "title": "title",
  "description": "description with hashtags",
  "hashtags": ["#AI", "#Technology"],
  "tags": ["AI", "artificial intelligence"],
  "hook": "strong opening hook",
  "slug": "short-topic-slug"
}}
"""

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"models/{MODEL}:generateContent"
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

        try:
            print(f"Gemini attempt {attempt}/5...")

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=90
            )

            if response.status_code == 200:
                data = response.json()

                text = (
                    data["candidates"][0]["content"]["parts"][0]["text"]
                )

                # Remove accidental markdown fences.
                text = text.strip()
                text = re.sub(r"^```json", "", text)
                text = re.sub(r"^```", "", text)
                text = re.sub(r"```$", "", text)
                text = text.strip()

                package = json.loads(text)

                required = [
                    "topic",
                    "title",
                    "description",
                    "hashtags",
                    "tags",
                    "hook",
                    "slug",
                ]

                for key in required:
                    if key not in package:
                        raise ValueError(
                            f"Missing JSON field: {key}"
                        )

                return package

            print(
                "Gemini HTTP error:",
                response.status_code,
                response.text[:500]
            )

        except Exception as e:
            print("Gemini attempt failed:", e)

        if attempt < 5:
            time.sleep(attempt * 5)

    raise RuntimeError(
        "Gemini failed after 5 attempts."
    )


def save_package(package):
    """Save today's automation package."""

    package["channel"] = "TechMind Studio"
    package["generated_at"] = datetime.now(
        timezone.utc
    ).isoformat()

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

    print()
    print("=" * 60)
    print("CONTENT PACKAGE CREATED")
    print("=" * 60)
    print("Topic:", package["topic"])
    print("Title:", package["title"])
    print("Hook:", package["hook"])
    print("Hashtags:", ", ".join(package["hashtags"]))
    print("Tags:", ", ".join(package["tags"]))
    print("Saved:", OUTPUT_FILE)
    print("=" * 60)


def main():

    print("==============================================")
    print("TechMind Studio - AI Auto Publisher")
    print("==============================================")

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY secret is missing."
        )

    print("Fetching fresh AI news...")
    headlines = get_news()

    if headlines:
        print(f"Found {len(headlines)} recent headlines.")
    else:
        print(
            "No news headlines available. "
            "Gemini will still generate a topic."
        )

    print("Generating fresh content package...")

    package = generate_content(headlines)

    save_package(package)

    print()
    print("Automation backbone step completed.")
    print("Video generation remains disabled for now.")
    print("Next module will consume content_package.json.")


if __name__ == "__main__":
    main()
