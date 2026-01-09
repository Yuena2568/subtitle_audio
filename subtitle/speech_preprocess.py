from __future__ import annotations

from dataclasses import dataclass
from typing import List
import re


@dataclass
class SpeechSegment:
    """
    专门用于 TTS 的 Segment
    """
    index: int
    start: float   # seconds
    end: float     # seconds
    text: str


# -------------------------
# 基础工具
# -------------------------

_PUNCT_RE = re.compile(r"[。！？.!?]$")


def _normalize_text(text: str) -> str:
    """
    基础清洗：
    - 去首尾空格
    - 合并多余空白
    """
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _ends_sentence(text: str) -> bool:
    """是否明显是句子结束"""
    return bool(_PUNCT_RE.search(text))


def _text_diff(prev: str, curr: str) -> str:
    """
    关键函数：字幕递增去重

    如果 curr 以 prev 开头：
        返回 curr 中「新增的那一段」
    否则：
        返回 curr
    """
    if not prev:
        return curr

    if curr.startswith(prev):
        diff = curr[len(prev):].lstrip()
        return diff

    return curr


# -------------------------
# 阶段 C-1：标准化
# -------------------------

def normalize_segments(segments) -> List[SpeechSegment]:
    """
    将原始 Segment 转成 SpeechSegment
    """
    out: List[SpeechSegment] = []

    for i, seg in enumerate(segments, start=1):
        text = _normalize_text(seg.text)
        if not text:
            continue

        out.append(
            SpeechSegment(
                index=i,
                start=float(seg.start),
                end=float(seg.end),
                text=text,
            )
        )

    return out


# -------------------------
# 阶段 C-2：字幕递增去重（最关键）
# -------------------------

def deduplicate_segments(segments: List[SpeechSegment]) -> List[SpeechSegment]:
    """
    去掉 YouTube / WebVTT 的递增重复内容
    """
    out: List[SpeechSegment] = []
    prev_text = ""

    for seg in segments:
        diff = _text_diff(prev_text, seg.text)
        diff = diff.strip()

        if not diff:
            # 完全是重复 → 丢弃
            prev_text = seg.text
            continue

        out.append(
            SpeechSegment(
                index=seg.index,
                start=seg.start,
                end=seg.end,
                text=diff,
            )
        )

        prev_text = seg.text

    return out


# -------------------------
# 阶段 C-3：语音友好合并
# -------------------------

def merge_segments_for_speech(
    segments: List[SpeechSegment],
    max_gap: float = 0.4,
    short_len: int = 20,
) -> List[SpeechSegment]:
    """
    合并：
    - 时间非常接近
    - 文本很短
    - 不是完整句子
    """
    if not segments:
        return []

    merged: List[SpeechSegment] = []
    buffer = segments[0]

    for curr in segments[1:]:
        gap = curr.start - buffer.end

        should_merge = (
            gap >= 0
            and gap <= max_gap
            and len(buffer.text) <= short_len
            and not _ends_sentence(buffer.text)
        )

        if should_merge:
            buffer = SpeechSegment(
                index=buffer.index,
                start=buffer.start,
                end=curr.end,
                text=f"{buffer.text} {curr.text}".strip(),
            )
        else:
            merged.append(buffer)
            buffer = curr

    merged.append(buffer)
    return merged


# -------------------------
# 阶段 C-4：重算语音时间轴
# -------------------------

def reassign_speech_timeline(
    segments: List[SpeechSegment],
    char_rate: float = 0.18,
) -> List[SpeechSegment]:
    """
    调整 end 时间，保证语音不会被压缩
    """
    out: List[SpeechSegment] = []

    for seg in segments:
        min_duration = max(0.4, len(seg.text) * char_rate)
        original_duration = max(0.0, seg.end - seg.start)

        duration = max(original_duration, min_duration)

        out.append(
            SpeechSegment(
                index=seg.index,
                start=seg.start,
                end=seg.start + duration,
                text=seg.text,
            )
        )

    return out


# -------------------------
# 🚀 总入口（你在 tts.py 里只需要调用这个）
# -------------------------

def prepare_segments_for_tts(raw_segments) -> List[SpeechSegment]:
    """
    一步到位：
    raw_segments
      → normalize
      → deduplicate
      → merge
      → timeline fix
    """
    s1 = normalize_segments(raw_segments)
    s2 = deduplicate_segments(s1)
    s3 = merge_segments_for_speech(s2)
    s4 = reassign_speech_timeline(s3)
    return s4
