import os
import json
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# ============================================================
# TECHMIND STUDIO
# YOUTUBE UPLOADER
# ============================================================

TOKEN_ENV = "YOUTUBE_TOKEN_JSON"

VIDEO_FILE = Path("techmind_studio_long.mp4")
PACKAGE_FILE = Path("content_package.json")


# ============================================================
# HELPERS
# ============================================================

def fail(message):
    print("")
    print("ERROR:", message)
    print("")
    sys.exit(1)


def load_package():
    if not PACKAGE_FILE.exists():
        fail("content_package.json not found.")

    try:
        with open(
            PACKAGE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    except Exception as error:
        fail(
            "Could not read content_package.json: "
            + str(error)
        )


def load_credentials():
    token_json = os.environ.get(
        TOKEN_ENV,
        ""
    ).strip()

    if not token_json:
        fail(
            "YOUTUBE_TOKEN_JSON GitHub secret is missing."
        )

    try:
        token_data = json.loads(
            token_json
        )

    except Exception as error:
        fail(
            "YOUTUBE_TOKEN_JSON is not valid JSON: "
            + str(error)
        )

    scopes = [
        "https://www.googleapis.com/auth/youtube.upload"
    ]

    try:
        credentials = Credentials.from_authorized_user_info(
            token_data,
            scopes=scopes
        )

    except Exception as error:
        fail(
            "Could not load YouTube credentials: "
            + str(error)
        )

    if not credentials.valid:
        fail(
            "YouTube credentials are not valid."
        )

    return credentials


# ============================================================
# YOUTUBE SERVICE
# ============================================================

def create_youtube_service(credentials):

    try:
        return build(
            "youtube",
            "v3",
            credentials=credentials
        )

    except Exception as error:
        fail(
            "Could not connect to YouTube API: "
            + str(error)
        )


# ============================================================
# METADATA
# ============================================================

def build_description(data):

    description = str(
        data.get(
            "description",
            ""
        )
    ).strip()

    hashtags = data.get(
        "hashtags",
        []
    )

    if not isinstance(
        hashtags,
        list
    ):
        hashtags = []

    hashtag_text = " ".join(
        str(tag).strip()
        for tag in hashtags
        if str(tag).strip()
    )

    if hashtag_text:
        if hashtag_text not in description:
            description += (
                "\n\n"
                + hashtag_text
            )

    return description.strip()


def build_tags(data):

    tags = data.get(
        "tags",
        []
    )

    if not isinstance(
        tags,
        list
    ):
        return []

    clean_tags = []

    for tag in tags:
        tag = str(tag).strip()

        if tag and tag not in clean_tags:
            clean_tags.append(tag)

    return clean_tags[:15]


# ============================================================
# UPLOAD
# ============================================================

def upload_video(
    youtube,
    data
):

    if not VIDEO_FILE.exists():
        fail(
            "techmind_studio_long.mp4 not found."
        )

    title = str(
        data.get(
            "title",
            "TechMind Studio"
        )
    ).strip()

    description = build_description(
        data
    )

    tags = build_tags(
        data
    )

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "28"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    print("")
    print(
        "=========================================="
    )
    print(
        "TechMind Studio - YouTube Upload"
    )
    print(
        "=========================================="
    )

    print(
        "Title:",
        title
    )

    print(
        "Video:",
        VIDEO_FILE
    )

    print(
        "Privacy:",
        "public"
    )

    print(
        "Tags:",
        len(tags)
    )

    print(
        "Starting upload..."
    )

    media = MediaFileUpload(
        str(VIDEO_FILE),
        mimetype="video/mp4",
        resumable=True,
        chunksize=8 * 1024 * 1024
    )

    try:

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None

        while response is None:

            status, response = request.next_chunk()

            if status:
                progress = int(
                    status.progress() * 100
                )

                print(
                    f"Upload progress: {progress}%"
                )

        video_id = response.get(
            "id"
        )

        if not video_id:
            fail(
                "YouTube upload returned no video ID."
            )

        print("")
        print(
            "=========================================="
        )
        print(
            "YOUTUBE UPLOAD SUCCESSFUL"
        )
        print(
            "=========================================="
        )

        print(
            "Video ID:",
            video_id
        )

        print(
            "YouTube URL:",
            "https://www.youtube.com/watch?v="
            + video_id
        )

        print(
            "=========================================="
        )

        return video_id

    except Exception as error:

        fail(
            "YouTube upload failed: "
            + str(error)
        )


# ============================================================
# MAIN
# ============================================================

def main():

    data = load_package()

    credentials = load_credentials()

    youtube = create_youtube_service(
        credentials
    )

    upload_video(
        youtube,
        data
    )


if __name__ == "__main__":
    main()
