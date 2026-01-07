from subtitle.loader import load_text
from subtitle.segmenter import segment_text
from subtitle.rewriter import rewrite_segment
from subtitle.ai_rewriter import ai_rewrite_segment
from subtitle.model import Segment


def run_pipeline(
    input_path: str,
    use_ai_rewrite: bool = False,
) -> list[Segment]:

    text = load_text(input_path)
    segments = segment_text(text)

    final: list[Segment] = []
    for seg in segments:
        seg = rewrite_segment(seg)
        if use_ai_rewrite:
            seg = ai_rewrite_segment(seg)
        final.append(seg)

    return final
