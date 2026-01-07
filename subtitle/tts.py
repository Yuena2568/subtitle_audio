# subtitle/tts.py
import subprocess
import sys
import time
from typing import List
from subtitle.model import Segment


def speak(text: str) -> None:
    if not text.strip():
        return

    try:
        if sys.platform == "darwin":
            subprocess.run(["say", text], check=False)

        elif sys.platform.startswith("linux"):
            subprocess.run(["espeak", text], check=False)

        elif sys.platform == "win32":
            subprocess.run(
                [
                    "powershell",
                    "-Command",
                    (
                        'Add-Type -AssemblyName System.Speech; '
                        '(New-Object System.Speech.Synthesis.SpeechSynthesizer)'
                        f'.Speak("{text}")'
                    ),
                ],
                check=False,
            )
        else:
            print("TTS not supported on this platform.")

    except Exception as e:
        print(f"TTS failed: {e}")


def speak_segments(
    segments: List[Segment],
    pause: float = 0.3,
) -> None:
    """
    Speak segments one by one.
    """
    total = len(segments)

    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue

        print(f"[TTS] {seg.index}/{total}")
        speak(text)
        time.sleep(pause)
