from typing import List
from subtitle.model import Segment


def segments_to_text(segments: List[Segment]) -> str:
    return "\n\n".join(seg.text for seg in segments)
