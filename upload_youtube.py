
import os
import json
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


# ============================================================
# TECHMIND STUDIO — YOUTUBE UPLOADER
# Supports long videos, Shorts, metadata, tags and thumbnails
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

TOKEN_ENV = "YOUTUBE_TOKEN_JSON"

LONG_VIDEO_FILE = BASE_DIR / "techmind_studio_long.mp4"
SHORT_VIDEO_FILE = BASE_DIR / "techmind_studio_short.mp4"
PACKAGE_FILE = BASE_DIR / "content_package.json"
THUMBNAIL_FILE = BASE_DIR / "thumbnail.jpg"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

CATEGORY_ID = "28"  # Science & Technology


def log(message):
    print(f"[TechMind Studio] {message}", flush=True)


def load_token():
    raw_token = os.environ.get(TOKEN_ENV)

    if not raw_token:
        raise RuntimeError(
            f"Missing GitHub Actions secret: {TOKEN_ENV}"
        )

    try:
        token_data = json.loads(raw_token)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{TOKEN_ENV} must contain valid JSON."
        ) from exc

    credentials = Credentials.from_authorized_user_info(
        token_data,
        scopes=SCOPES,
    )

    if credentials.expired and credentials.refresh_token:
        log("Refreshing YouTube access token...")
        credentials.refresh(Request())

    if not credentials.valid:
        raise RuntimeError(
            "YouTube credentials are invalid. "
            "Refresh the OAuth token and update the GitHub secret."
        )

    return credentials


def load_package():
    if not PACKAGE_FILE.exists():
        raise FileNotFoundError(
            f"Content package not found: {PACKAGE_FILE.name}"
        )

    with PACKAGE_FILE.open("r", encoding="utf-8") as file:
        package = json.load(file)

    if not isinstance(package, dict):
        raise ValueError("Content package must be a JSON object.")

    return package


def get_text(package, *keys, default=""):
    for key in keys:
        value = package.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return default


def get_tags(package):
    tags = package.get("tags", package.get("youtube_tags", []))

    if isinstance(tags, str):
        tags = [
            item.strip().lstrip("#")
            for item in tags.split(",")
            if item.strip()
        ]

    if not isinstance(tags, list):
        return []

    clean_tags = []
    seen = set()

    for tag in tags:
        if not isinstance(tag, str):
            continue

        tag = tag.strip().lstrip("#")

        if tag and tag.lower() not in seen:
            clean_tags.append(tag)
            seen.add(tag.lower())

    # YouTube video tags have a 500-character total limit.
    result = []
    total = 0

    for tag in clean_tags:
        extra = len(tag) + (1 if result else 0)

        if total + extra > 500:
            break

        result.append(tag)
        total += extra

    return result


def get_hashtags(package, description):
    hashtags = package.get("hashtags", [])

    if isinstance(hashtags, str):
        hashtags = hashtags.split()

    if not isinstance(hashtags, list):
        hashtags = []

    clean = []

    for hashtag in hashtags:
        if not isinstance(hashtag, str):
            continue

        hashtag = hashtag.strip().replace(" ", "")
        hashtag = hashtag.lstrip("#")

        if hashtag and hashtag.replace("_", "").isalnum():
            clean.append("#" + hashtag)

    # Preserve hashtags already included in the description.
    for hashtag in description.split():
        if hashtag.startswith("#"):
            normalized = hashtag.strip(".,!?;:")
            if normalized not in clean:
                clean.append(normalized)

    # Add a brand hashtag if none exists.
    if not any(tag.lower() == "#techmindstudio" for tag in clean):
        clean.append("#TechMindStudio")

    return list(dict.fromkeys(clean))[:10]


def prepare_metadata(package, is_short=False):
    title = get_text(
        package,
        "short_title" if is_short else "title",
        "title",
        default="AI Tutorial | TechMind Studio",
    )

    # YouTube titles must not exceed 100 characters.
    title = title[:100].strip()

    description = get_text(
        package,
        "short_description" if is_short else "description",
        "description",
        default="Learn more about AI with TechMind Studio.",
    )

    hashtags = get_hashtags(package, description)

    # Append hashtags only when they are not already present.
    existing = set(description.split())
    missing = [tag for tag in hashtags if tag not in existing]

    if missing:
        description = description.rstrip() + "\n\n" + " ".join(missing)

    description = description[:5000]

    tags = get_tags(package)

    return {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": CATEGORY_ID,
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": os.environ.get(
                "YOUTUBE_PRIVACY_STATUS", "public"
            ),
            "selfDeclaredMadeForKids": False,
        },
    }


def upload_video(youtube, video_path, package, is_short=False):
    if not video_path.is_file():
        log(f"Skipping missing file: {video_path.name}")
        return None

    if video_path.stat().st_size == 0:
        raise ValueError(f"Video file is empty: {video_path.name}")

    metadata = prepare_metadata(package, is_short=is_short)

    log(f"Uploading {'Short' if is_short else 'long video'}...")
    log(f"Title: {metadata['snippet']['title']}")

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        chunksize=8 * 1024 * 1024,
        resumable=True,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=metadata,
        media_body=media,
    )

    response = None

    while response is None:
        status, response = request.next_chunk()

        if status:
            log(f"Upload progress: {int(status.progress() * 100)}%")

    video_id = response.get("id")

    if not video_id:
        raise RuntimeError("YouTube did not return a video ID.")

    log(f"Upload successful: https://www.youtube.com/watch?v={video_id}")

    # A Short is determined by YouTube based on video properties,
    # not simply by setting a metadata flag.
    if not is_short and THUMBNAIL_FILE.is_file():
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(
                    str(THUMBNAIL_FILE),
                    mimetype="image/jpeg",
                ),
            ).execute()

            log("Custom thumbnail uploaded.")
        except HttpError as exc:
            log(f"Thumbnail upload failed: {exc}")

    return video_id


def main():
    log("Starting YouTube upload pipeline...")

    package = load_package()
    credentials = load_token()

    youtube = build(
        "youtube",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )

    uploaded = []

    # Upload long-form video first.
    long_id = upload_video(
        youtube,
        LONG_VIDEO_FILE,
        package,
        is_short=False,
    )

    if long_id:
        uploaded.append({
            "type": "long",
            "video_id": long_id,
        })

    # Upload a Short only when the creator has generated one.
    short_id = upload_video(
        youtube,
        SHORT_VIDEO_FILE,
        package,
        is_short=True,
    )

    if short_id:
        uploaded.append({
            "type": "short",
            "video_id": short_id,
        })

    if not uploaded:
        raise RuntimeError(
            "No videos were uploaded. Check generated MP4 files."
        )

    result_file = BASE_DIR / "upload_results.json"

    with result_file.open("w", encoding="utf-8") as file:
        json.dump(uploaded, file, indent=2)

    log(f"Finished. Uploaded {len(uploaded)} video(s).")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log(f"ERROR: {exc}")
        sys.exit(1)
