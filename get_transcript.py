"""
YouTube Transcript Downloader
Usage: python get_transcript.py <video_url_or_id> [sprache]
       python get_transcript.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
       python get_transcript.py dQw4w9WgXcQ de
       python get_transcript.py dQw4w9WgXcQ en
"""

import sys
import re
import os
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled


def extract_video_id(url_or_id: str) -> str:
    """Extrahiert die Video-ID aus einer URL oder gibt die ID direkt zurück."""
    patterns = [
        r"(?:v=|youtu\.be/|embed/|shorts/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    raise ValueError(f"Keine gültige YouTube-URL oder Video-ID: {url_or_id}")


def get_transcript(video_id: str, sprachen: list[str] = None) -> tuple[str, str]:
    """Lädt das Transkript und gibt (text, sprache) zurück."""
    api = YouTubeTranscriptApi()

    try:
        transcript_list = api.list(video_id)

        # Verfügbare Sprachen anzeigen
        verfuegbar = [t.language_code for t in transcript_list]
        print(f"Verfügbare Sprachen: {verfuegbar}")

        # Gewünschte Sprachen versuchen, sonst erste verfügbare
        if sprachen:
            transcript = transcript_list.find_transcript(sprachen)
        else:
            # Deutsch bevorzugen, dann Englisch, dann was auch immer verfügbar ist
            try:
                transcript = transcript_list.find_transcript(["de", "en"])
            except NoTranscriptFound:
                transcript = transcript_list.find_transcript(verfuegbar)

        snippets = transcript.fetch()
        sprache = transcript.language_code

        # Text zusammensetzen
        text = "\n".join(s.text for s in snippets)
        return text, sprache

    except TranscriptsDisabled:
        raise RuntimeError("Transkripte sind für dieses Video deaktiviert.")
    except NoTranscriptFound:
        raise RuntimeError(f"Kein Transkript in den gewünschten Sprachen gefunden.")


def save_transcript(video_id: str, text: str, sprache: str, output_dir: str = "transcripts") -> str:
    """Speichert das Transkript als .txt-Datei."""
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{video_id}_{sprache}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(text)
    return filename


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    url_or_id = sys.argv[1]
    sprachen = sys.argv[2:] if len(sys.argv) > 2 else None

    try:
        video_id = extract_video_id(url_or_id)
        print(f"Video-ID: {video_id}")

        text, sprache = get_transcript(video_id, sprachen)
        filename = save_transcript(video_id, text, sprache)

        print(f"Gespeichert: {filename}")
        print(f"Zeichen: {len(text):,}")

    except (ValueError, RuntimeError) as e:
        print(f"Fehler: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
