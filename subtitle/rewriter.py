from subtitle.model import Segment


def rewrite_segment(seg: Segment) -> Segment:
    return Segment(
        index=seg.index,
        text=seg.text.strip(),
    )
