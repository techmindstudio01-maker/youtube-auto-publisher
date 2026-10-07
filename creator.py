name: AI Auto Publisher

on:
  workflow_dispatch:

  schedule:
    - cron: "30 12 * * *"

permissions:
  contents: write

jobs:
  publish:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install system packages
        run: |
          sudo apt-get update
          sudo apt-get install -y ffmpeg

      - name: Install Python packages
        run: |
          python -m pip install --upgrade pip
          pip install \
            requests \
            edge-tts \
            google-api-python-client \
            google-auth \
            google-auth-oauthlib \
            google-auth-httplib2

      - name: Run AI Creator
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          YOUTUBE_TOKEN_JSON: ${{ secrets.YOUTUBE_TOKEN_JSON }}
          YOUTUBE_PRIVACY: public
        run: |
          python creator.py

      - name: Save production files
        if: always()
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

          git add production/ || true

          git diff --cached --quiet || git commit -m "AI generated production"

          git push || true
