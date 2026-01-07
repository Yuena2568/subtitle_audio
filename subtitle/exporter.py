# subtitle/exporter.py
import json
from typing import List
from subtitle.model import Segment


def export_segments(segments: List[Segment], path: str) -> None:
    """
    Export segments to JSON or JSONL.

    Args:
        segments: list of Segment
        path: output file path (.json or .jsonl)
    """
    if path.endswith(".jsonl"):
        with open(path, "w", encoding="utf-8") as f:
            for s in segments:
                f.write(json.dumps({"index": s.index, "text": s.text}, ensure_ascii=False) + "\n")
    else:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                [{"index": s.index, "text": s.text} for s in segments],
                f,
                ensure_ascii=False,
                indent=2,
            )
