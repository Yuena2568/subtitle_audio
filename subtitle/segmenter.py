from typing import List
from subtitle.model import Segment

MIN_CHARS = 40


def _is_numeric_line(line: str) -> bool:
    return line.isdigit()


def _is_timestamp_line(line: str) -> bool:
    return "-->" in line and ":" in line


def segment_text(text: str) -> List[Segment]:
    lines = text.splitlines()
    raw_lines: List[str] = []

    # 1. 清理 srt 噪声
    for line in lines:
        line = line.strip()

        if not line:
            continue
        if _is_numeric_line(line):
            continue
        if _is_timestamp_line(line):
            continue

        raw_lines.append(line)

    # 2. 合并为“适合听”的段落
    segments: List[Segment] = []
    buffer = ""
    index = 1

    for line in raw_lines:
        if not buffer:
            buffer = line
            continue

        if len(buffer) < MIN_CHARS:
            buffer = buffer + " " + line
        else:
            segments.append(Segment(index=index, text=buffer))
            index += 1
            buffer = line

    if buffer:
        segments.append(Segment(index=index, text=buffer))

    return segments
