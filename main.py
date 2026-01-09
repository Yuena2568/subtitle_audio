import argparse
from pathlib import Path
import traceback
from typing import List

from subtitle.segmenter import parse_txt, parse_vtt
from subtitle.pipeline import run_pipeline
from subtitle.exporter import export_segments
from subtitle.tts import speak_segments, synthesize_audio_timeline
from subtitle.video import replace_audio_in_video
from subtitle.asr import extract_audio, audio_to_segments
from subtitle.asr_compare import process_with_asr_comparison


def process_single_file(
    file_path: str,
    *,
    vtt_file: str | None = None,
    ai_rewrite: bool = False,
    model_path: str | None = None,
    translate: bool = False,
    tts: bool = False,
    live_tts: bool = False,
    export: bool = False,
    language: str = "zh",
    video_replace: str | None = None,
    use_asr_compare: bool = False,
    whisper_model: str = "small",
    enable_weight_filter: bool = True,
    min_weight: float = 0.4,
):
    """
    处理单个文件
    
    Args:
        use_asr_compare: 是否使用 ASR 对比融合（推荐，质量更好）
        whisper_model: Whisper 模型大小（tiny/base/small/medium/large）
        enable_weight_filter: 是否启用权重筛选（默认 True）
        min_weight: 最小权重阈值（默认 0.4，低于此值的段落将被删除）
    """
    print(f"[File] Processing: {file_path}")
    file_path = Path(file_path)

    # ==================================================
    # 0️⃣ 生成 Segment 流（ASR对比 / VTT / TXT / ASR）
    # ==================================================
    
    # 如果启用 ASR 对比，使用新的融合流程
    if use_asr_compare:
        # 需要视频文件和可选的 VTT 文件
        if file_path.suffix.lower() not in [".mp4", ".avi", ".mkv", ".flv", ".webm", ".mov"]:
            print("[Warning] ASR 对比需要视频文件，切换到普通模式")
            use_asr_compare = False
    
    if use_asr_compare:
        print("\n[模式] 使用 ASR 对比融合模式（推荐）")
        try:
            segments = process_with_asr_comparison(
                video_path=str(file_path),
                vtt_path=vtt_file,
                whisper_model=whisper_model,
                enable_weight_filter=enable_weight_filter,
                min_weight=min_weight
            )
        except Exception as e:
            print(f"[Error] ASR 对比失败: {e}")
            print("[Fallback] 回退到普通 VTT 解析模式")
            # 回退到普通模式
            if vtt_file:
                segments = parse_vtt(vtt_file)
            else:
                segments = []
    elif vtt_file:
        # 如果明确指定了 VTT 文件，使用它
        segments = parse_vtt(vtt_file)
        # parse_vtt 内部已经打印了日志
    elif file_path.suffix.lower() in [".srt", ".txt", ".vtt", ".json"]:
        # 识别字幕文件（SRT、TXT、VTT、JSON）
        segments = parse_txt(str(file_path))
        # parse_txt/parse_srt/parse_vtt/parse_json 内部已经打印了日志
    else:
        # 其他文件类型，尝试作为视频文件进行 ASR（不使用对比）
        audio_path = file_path.with_suffix(".wav")
        extract_audio(str(file_path), str(audio_path))
        segments = audio_to_segments(str(audio_path), model_size=whisper_model)
        print(f"[INFO] {len(segments)} segments generated from ASR")

    if not segments:
        print("[Warning] No segments generated")
        return []

    # ==================================================
    # 1️⃣ Pipeline（文本处理）
    # ==================================================
    new_segments = run_pipeline(
        segments=segments,
        ai_rewrite=ai_rewrite,
        model_path=model_path,
        translate=translate,
        tts=False,
        language=language,
        optimize_json=True,
    )

    for seg in new_segments[:5]:
        print(f"[Segment] {seg.index}: {seg.text[:60]}")

    # ==================================================
    # 2️⃣ 导出字幕
    # ==================================================
    if export:
        base = file_path.with_suffix("")
        # 将 Segment 对象转换为字典
        segments_dict = [seg.to_dict() for seg in new_segments]
        export_segments(segments_dict, str(base), format="srt")
        export_segments(segments_dict, str(base), format="json")
        print("[Export] Subtitle exported")

    # ==================================================
    # 3️⃣ 即时朗读（CLI 预览）
    # ==================================================
    if live_tts:
        speak_segments(new_segments)

    # ==================================================
    # 4️⃣ 时间轴 TTS
    # ==================================================
    audio_out = None
    if tts:
        try:
            audio_out = synthesize_audio_timeline(
                new_segments,
                str(file_path.with_suffix(".mp3")),
            )
            print(f"[TTS] Audio generated: {audio_out}")
        except Exception as e:
            print("[Error] TTS failed")
            traceback.print_exc()

    # ==================================================
    # 5️⃣ 视频替换音轨
    # ==================================================
    if video_replace and audio_out:
        try:
            out_video = replace_audio_in_video(video_replace, audio_out)
            print(f"[Video] Output: {out_video}")
        except Exception:
            print("[Error] Video replace failed")
            traceback.print_exc()

    return new_segments


def process_batch(
    input_dir: str,
    *,
    output_dir: str | None = None,
    pattern: str = "*.vtt",
    ai_rewrite: bool = False,
    model_path: str | None = None,
    translate: bool = False,
    tts: bool = False,
    export: bool = True,  # 批量处理默认导出
    language: str = "zh",
    video_replace: bool = False,
    use_asr_compare: bool = False,
    whisper_model: str = "small",
    enable_weight_filter: bool = True,
    min_weight: float = 0.4,
) -> List[Path]:
    """
    批量处理目录中的字幕文件
    
    Args:
        input_dir: 输入目录路径
        output_dir: 输出目录路径（如果为 None，则在输入目录下创建 output 子目录）
        pattern: 文件匹配模式，例如 "*.vtt", "*.srt", "*.txt"
        ai_rewrite: 是否启用 AI Rewrite
        model_path: AI 模型路径
        translate: 是否翻译
        tts: 是否生成 TTS
        export: 是否导出字幕文件
        language: 目标语言
        video_replace: 是否替换视频音轨（需要同名视频文件）
    
    Returns:
        处理成功的文件列表
    """
    input_path = Path(input_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"输入目录不存在: {input_dir}")
    
    # 设置输出目录
    if output_dir:
        output_path = Path(output_dir)
    else:
        output_path = input_path / "output"
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 查找匹配的文件
    files = list(input_path.glob(pattern))
    if not files:
        print(f"[Batch] 在 {input_dir} 中未找到匹配 {pattern} 的文件")
        return []
    
    print(f"[Batch] 找到 {len(files)} 个文件，开始批量处理...")
    print(f"[Batch] 输出目录: {output_path}")
    
    success_files = []
    failed_files = []
    
    for idx, file in enumerate(files, 1):
        print(f"\n{'='*60}")
        print(f"[Batch] [{idx}/{len(files)}] 处理文件: {file.name}")
        print(f"{'='*60}")
        
        try:
            # 确定输出文件路径（在输出目录中）
            output_base = output_path / file.stem
            
            # 检查是否有对应的视频文件
            video_file = None
            video_extensions = [".mp4", ".avi", ".mkv", ".flv", ".webm"]
            for ext in video_extensions:
                potential_video = input_path / f"{file.stem}{ext}"
                if potential_video.exists():
                    video_file = potential_video
                    break
            
            # 处理文件（使用绝对路径）
            segments = process_single_file(
                str(file.absolute()),  # 使用绝对路径
                vtt_file=None,  # 批量模式下直接使用文件路径
                ai_rewrite=ai_rewrite,
                model_path=model_path,
                translate=translate,
                tts=tts,
                live_tts=False,  # 批量处理不启用即时朗读
                export=export,
                language=language,
                video_replace=str(video_file.absolute()) if video_replace and video_file else None,
                use_asr_compare=use_asr_compare,
                whisper_model=whisper_model,
                enable_weight_filter=enable_weight_filter,
                min_weight=min_weight,
            )
            
            if segments:
                # 将生成的文件移动到输出目录
                if export:
                    # 查找在原目录生成的文件并移动到输出目录
                    for ext in [".srt", ".json"]:
                        generated_file = file.with_suffix(ext)
                        if generated_file.exists():
                            dest_file = output_path / generated_file.name
                            # 如果目标文件已存在，先删除
                            if dest_file.exists():
                                dest_file.unlink()
                            generated_file.rename(dest_file)
                            print(f"[Batch] 已移动 {generated_file.name} -> {dest_file}")
                
                success_files.append(file)
                print(f"[Batch] [OK] 成功处理: {file.name}")
            else:
                failed_files.append(file)
                print(f"[Batch] [FAIL] 处理失败（无输出）: {file.name}")
                
        except Exception as e:
            failed_files.append(file)
            print(f"[Batch] [FAIL] 处理失败: {file.name}")
            print(f"[Batch] 错误信息: {e}")
            traceback.print_exc()
    
    # 输出总结
    print(f"\n{'='*60}")
    print(f"[Batch] 批量处理完成！")
    print(f"  成功: {len(success_files)} 个文件")
    print(f"  失败: {len(failed_files)} 个文件")
    if failed_files:
        print(f"  失败文件列表:")
        for f in failed_files:
            print(f"    - {f.name}")
    print(f"{'='*60}")
    
    return success_files


def main():
    parser = argparse.ArgumentParser(
        "Subtitle Audio Processing CLI",
        description="批量处理视频字幕：智能优化、风格化、翻译、TTS 全流程工具"
    )

    # 处理模式：单文件或批量
    parser.add_argument("--file", type=str, help="处理单个文件（与 --dir 二选一）")
    parser.add_argument("--dir", type=str, help="批量处理目录（与 --file 二选一）")
    parser.add_argument("--vtt", type=str, help="VTT 字幕文件路径（单文件模式）")
    parser.add_argument("--pattern", type=str, default="*.vtt", help="批量处理时的文件匹配模式（默认: *.vtt）")
    parser.add_argument("--output-dir", type=str, help="批量处理时的输出目录（默认: input_dir/output）")
    
    # 处理选项
    parser.add_argument("--ai-rewrite", action="store_true", help="启用 AI Rewrite")
    parser.add_argument("--model-path", type=str, help="AI 模型路径（启用 --ai-rewrite 时必需）")
    parser.add_argument("--translate", action="store_true", help="启用翻译功能")
    parser.add_argument("--tts", action="store_true", help="生成 TTS 音频")
    parser.add_argument("--live-tts", action="store_true", help="即时朗读（仅单文件模式）")
    parser.add_argument("--export", action="store_true", default=True, help="导出字幕文件（默认启用）")
    parser.add_argument("--no-export", action="store_false", dest="export", help="不导出字幕文件")
    parser.add_argument("--language", type=str, default="zh", help="目标语言: zh/en（默认: zh）")
    parser.add_argument("--video-replace", type=str, help="替换视频音轨（单文件模式，指定视频路径）")
    parser.add_argument("--batch-video-replace", action="store_true", help="批量处理时自动替换同名视频音轨")
    parser.add_argument("--use-asr-compare", action="store_true", help="使用 ASR 对比融合模式（推荐，质量更好，需要视频文件）")
    parser.add_argument("--whisper-model", type=str, default="small", choices=["tiny", "base", "small", "medium", "large"], help="Whisper 模型大小（默认: small）")
    parser.add_argument("--enable-weight-filter", action="store_true", default=True, help="启用权重筛选（默认启用，删除低权重段落）")
    parser.add_argument("--no-weight-filter", action="store_false", dest="enable_weight_filter", help="禁用权重筛选")
    parser.add_argument("--min-weight", type=float, default=0.4, help="最小权重阈值（0-1，默认 0.4，低于此值的段落将被删除）")

    args = parser.parse_args()

    # 检查参数
    if not args.file and not args.dir:
        parser.error("必须指定 --file 或 --dir 参数之一")
    
    if args.file and args.dir:
        parser.error("--file 和 --dir 不能同时使用")

    # 单文件处理模式
    if args.file:
        process_single_file(
            args.file,
            vtt_file=args.vtt,
            ai_rewrite=args.ai_rewrite,
            model_path=args.model_path,
            translate=args.translate,
            tts=args.tts,
            live_tts=args.live_tts,
            export=args.export,
            language=args.language,
            video_replace=args.video_replace,
            use_asr_compare=args.use_asr_compare,
            whisper_model=args.whisper_model,
            enable_weight_filter=args.enable_weight_filter,
            min_weight=args.min_weight,
        )
    
    # 批量处理模式
    elif args.dir:
        process_batch(
            args.dir,
            output_dir=args.output_dir,
            pattern=args.pattern,
            ai_rewrite=args.ai_rewrite,
            model_path=args.model_path,
            translate=args.translate,
            tts=args.tts,
            export=args.export,
            language=args.language,
            video_replace=args.batch_video_replace,
            use_asr_compare=args.use_asr_compare,
            whisper_model=args.whisper_model,
            enable_weight_filter=args.enable_weight_filter,
            min_weight=args.min_weight,
        )


if __name__ == "__main__":
    main()
