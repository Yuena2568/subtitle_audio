# subtitle/exporter.py
from pathlib import Path
from typing import List, Dict
import json

def export_srt(segments: List[Dict], output_path: str) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for seg in segments:
            index = seg.get("index", 0)
            start = seg.get("start", 0)
            end = seg.get("end", 0)
            text = seg.get("text", "")
            f.write(f"{index}\n")
            f.write(f"{format_time(start)} --> {format_time(end)}\n")
            f.write(f"{text}\n\n")

def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def export_json(segments: List[Dict], output_path: str) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)

def export_segments(segments: List[Dict], base_path: str, format: str = "srt") -> None:
    """
    通用导出函数，根据格式导出字幕
    :param segments: 字幕段列表
    :param base_path: 基础路径（不含扩展名）
    :param format: 导出格式 ("srt" 或 "json")
    """
    if format == "srt":
        output_path = f"{base_path}.srt"
        export_srt(segments, output_path)
    elif format == "json":
        output_path = f"{base_path}.json"
        export_json(segments, output_path)
    else:
        raise ValueError(f"Unsupported format: {format}")
