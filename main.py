import argparse
from subtitle.pipeline import run_pipeline
from subtitle.output import segments_to_text
from subtitle.tts import speak_segments
from subtitle.exporter import export_segments
from subtitle.model import Segment  # 类型提示

def filter_segments(segments: list[Segment], pick: str | None) -> list[Segment]:
    """Filter segments for TTS according to --pick argument."""
    if not pick:
        return segments
    picks = {int(i) for i in pick.split(",")}
    return [s for s in segments if s.index in picks]


def main() -> None:
    parser = argparse.ArgumentParser(description="Subtitle Audio CLI (MVP)")

    parser.add_argument("input", type=str, help="Input subtitle file path")
    parser.add_argument("--ai-rewrite", action="store_true", help="Use AI to rewrite text for listening")
    parser.add_argument("--tts", action="store_true", help="Speak final text using system TTS")
    parser.add_argument("--pick", help="Comma separated segment indices to speak, e.g. 1,3,5")
    parser.add_argument("--export", help="Export segments to JSON or JSONL file")

    args = parser.parse_args()

    try:
        segments = run_pipeline(args.input, use_ai_rewrite=args.ai_rewrite)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    print(f"Final segments: {len(segments)}")
    print("----- preview -----")
    for seg in segments[:5]:
        print(f"- {seg.text}")
    print("----- end preview -----")

    final_text = segments_to_text(segments)

    # TTS 可控 pick
    if args.tts:
        tts_segments = filter_segments(segments, args.pick)
        speak_segments(tts_segments)

    # 导出 JSON / JSONL
    if args.export:
        export_segments(segments, args.export)
        print(f"[EXPORT] Segments exported to {args.export}")

    print("\n===== FINAL TEXT =====\n")
    print(final_text)


if __name__ == "__main__":
    main()
