"""
完整工作流脚本：从下载到最终视频生成
整合下载、ASR对比、翻译、TTS、视频换轨全流程
支持断点续传（每个步骤完成后保存进度）
"""
import os
import sys
from pathlib import Path
from typing import Optional

# 导入下载模块
try:
    from download_youtobe import download_youtube_video
    # 从下载模块获取下载根目录
    import download_youtobe
    DOWNLOAD_ROOT = download_youtobe.DOWNLOAD_ROOT
except ImportError:
    print("[Error] 无法导入 download_youtobe 模块")
    sys.exit(1)

# 导入处理模块
from main import process_single_file


def find_video_and_vtt(download_dir: str) -> tuple[str, Optional[str]]:
    """
    在下载目录中查找合并后的视频和VTT文件
    
    Args:
        download_dir: 下载根目录
    
    Returns:
        (video_path, vtt_path) 元组，vtt_path 可能为 None（如果没有VTT文件）
    
    Raises:
        FileNotFoundError: 如果找不到视频文件
    """
    download_path = Path(download_dir)
    
    if not download_path.exists():
        raise FileNotFoundError(f"下载目录不存在: {download_dir}")
    
    # 查找最新的下载目录（按修改时间排序）
    folders = sorted(
        [f for f in download_path.iterdir() if f.is_dir() and not f.name.startswith('.')],
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )
    
    if not folders:
        raise FileNotFoundError("未找到下载目录")
    
    latest_folder = folders[0]
    print(f"[工作流] 使用最新下载目录: {latest_folder.name}")
    
    # 查找合并后的视频（优先merged_video.mp4）
    merged_video = latest_folder / "merged_video.mp4"
    if not merged_video.exists():
        # 如果没有合并视频，查找第一个mp4文件
        mp4_files = list(latest_folder.glob("*.mp4"))
        if not mp4_files:
            raise FileNotFoundError(f"未找到视频文件: {latest_folder}")
        merged_video = mp4_files[0]
        print(f"[工作流] 使用视频文件: {merged_video.name}")
    
    # 查找VTT文件（优先.en.vtt，如果没有则查找.vtt）
    vtt_files = list(latest_folder.glob("*.en.vtt"))
    if not vtt_files:
        vtt_files = list(latest_folder.glob("*.vtt"))
    
    vtt_file = None
    if vtt_files:
        vtt_file = vtt_files[0]
        print(f"[工作流] 找到视频: {merged_video.name}")
        print(f"[工作流] 找到VTT: {vtt_file.name}")
    else:
        print(f"[工作流] 找到视频: {merged_video.name}")
        print(f"[工作流] ⚠️  未找到VTT字幕文件，将直接使用ASR模型生成字幕")
    
    return str(merged_video), str(vtt_file) if vtt_file else None


def complete_workflow(
    url: str,
    use_asr_compare: bool = True,
    whisper_model: str = "small",
    enable_weight_filter: bool = True,
    min_weight: float = 0.4,
    translate: bool = True,
    language: str = "zh",
    use_ai_rewrite: bool = False,
    model_path: Optional[str] = None,
    replace_video_audio: bool = True,
    use_ai_voice_clone: bool = False,  # 预留接口，暂未实现
    bgm_path: Optional[str] = None,
    bgm_volume: float = 0.25,
    voice: str = "zh-CN-XiaoxiaoNeural",
) -> bool:
    """
    完整工作流：下载 → ASR对比 → 翻译 → TTS → 视频换轨
    支持断点续传
    
    Args:
        url: YouTube视频URL
        use_asr_compare: 是否使用ASR对比（默认True）
        whisper_model: Whisper模型大小（默认small）
        enable_weight_filter: 是否启用权重筛选（默认True）
        min_weight: 最小权重阈值（默认0.4）
        translate: 是否翻译（默认True）
        language: 目标语言（默认zh）
        use_ai_rewrite: 是否使用AI改写（默认False，因为效果不好）
        model_path: AI改写模型路径（如果启用）
        replace_video_audio: 是否替换视频音轨（默认True）
        use_ai_voice_clone: 是否使用AI克隆语音（预留接口，暂未实现）
        voice: TTS 语音
    
    Returns:
        True 如果成功，False 如果失败
    """
    from subtitle.cache_manager import load_workflow_progress, save_workflow_progress, clear_workflow_progress
    
    print("=" * 60)
    print("完整工作流：从下载到最终视频生成")
    print("=" * 60)
    
    # 检查是否有未完成的进度
    progress = load_workflow_progress(DOWNLOAD_ROOT) if os.path.isdir(DOWNLOAD_ROOT) else None
    start_step = 1
    video_path = None
    vtt_path = None
    
    if progress and progress.get("last_step"):
        last_step = progress["last_step"]
        step_map = {
            "download": 1,
            "find_files": 2,
            "process": 3,
            "find_audio": 4,
            "replace_audio": 5,
        }
        if last_step in step_map:
            # 检查进度是否过期（超过24小时）
            import time
            elapsed = time.time() - progress.get("timestamp", 0)
            if elapsed > 86400:
                print(f"[工作流] 检测到旧的进度（{elapsed/3600:.1f}小时前），忽略并重新开始")
                clear_workflow_progress(DOWNLOAD_ROOT)
            else:
                resume_data = progress.get("steps", {}).get(last_step, {})
                saved_video = resume_data.get("video_path")
                saved_vtt = resume_data.get("vtt_path")
                if saved_video and Path(saved_video).exists():
                    print(f"[工作流] 检测到未完成的进度，上次步骤: {last_step}，自动续传")
                    start_step = step_map[last_step] + 1
                    video_path = saved_video
                    vtt_path = saved_vtt
                else:
                    print(f"[工作流] 进度文件中的视频路径已不存在，重新开始")
                    clear_workflow_progress(DOWNLOAD_ROOT)
    
    # 步骤1: 下载视频和字幕
    if start_step <= 1:
        print("\n[1/6] 下载视频和字幕...")
        print("=" * 60)
        try:
            download_youtube_video(url)
            print("\n✅ 下载完成！")
            save_workflow_progress(DOWNLOAD_ROOT, "download", {"url": url})
        except Exception as e:
            print(f"\n❌ 下载失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # 步骤2: 查找下载的文件
    if start_step <= 2:
        print("\n[2/6] 查找下载的文件...")
        print("=" * 60)
        try:
            video_path, vtt_path = find_video_and_vtt(DOWNLOAD_ROOT)
            if not vtt_path:
                # 如果没有VTT文件，强制使用ASR对比模式（会自动使用ASR生成字幕）
                print(f"[工作流] ⚠️  由于没有VTT文件，将使用ASR模型直接生成字幕")
                use_asr_compare = True  # 强制启用ASR模式
            save_workflow_progress(DOWNLOAD_ROOT, "find_files", {
                "video_path": video_path,
                "vtt_path": vtt_path,
                "use_asr_compare": use_asr_compare,
            })
        except Exception as e:
            print(f"\n❌ 查找文件失败: {e}")
            return False
    
    # 步骤3: ASR对比 + 翻译 + TTS
    if start_step <= 3:
        print("\n[3/6] ASR对比 + 翻译 + TTS...")
        print("=" * 60)
        try:
            # 处理视频：ASR对比 → 翻译 → TTS → 导出
            segments = process_single_file(
                file_path=video_path,
                vtt_file=vtt_path,
                use_asr_compare=use_asr_compare,
                whisper_model=whisper_model,
                enable_weight_filter=enable_weight_filter,
                min_weight=min_weight,
                translate=translate,
                language=language,
                tts=True,  # 生成TTS音频
                export=True,  # 导出JSON和SRT
                ai_rewrite=use_ai_rewrite,  # 默认False（效果不好）
                model_path=model_path,
                bgm_path=bgm_path,
                bgm_volume=bgm_volume,
                match_speech_rate=True,
                voice=voice,
            )
            
            if not segments:
                print("\n❌ 处理失败：未生成段落")
                return False
            
            print(f"\n✅ 处理完成：{len(segments)} 个段落")
            save_workflow_progress(DOWNLOAD_ROOT, "process", {
                "video_path": video_path,
                "vtt_path": vtt_path,
                "segment_count": len(segments),
            })
        except Exception as e:
            print(f"\n❌ 处理失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # 步骤4: 查找生成的音频文件
    if start_step <= 4:
        print("\n[4/6] 查找生成的音频文件...")
        print("=" * 60)
        video_path_obj = Path(video_path)
        audio_path = video_path_obj.with_suffix(".wav")
        
        if not audio_path.exists():
            print(f"\n❌ 音频文件不存在: {audio_path}")
            return False
        
        print(f"✅ 找到音频文件: {audio_path.name}")
        print(f"   文件大小: {audio_path.stat().st_size / (1024*1024):.2f} MB")
        save_workflow_progress(DOWNLOAD_ROOT, "find_audio", {
            "video_path": video_path,
            "audio_path": str(audio_path),
        })
    else:
        video_path_obj = Path(video_path)
        audio_path = video_path_obj.with_suffix(".wav")
    
    # 步骤5: 替换视频音轨（如果启用）
    if replace_video_audio and start_step <= 5:
        print("\n[5/6] 替换视频音轨...")
        print("=" * 60)
        try:
            from subtitle.video import replace_audio_in_video
            
            output_video = replace_audio_in_video(
                video_path_obj,
                str(audio_path),
                preserve_background=True,
                bgm_path=bgm_path,
                bgm_volume=bgm_volume,
                default_bgm_path=os.environ.get("SUBTITLE_DEFAULT_BGM"),
            )
            print(f"\n✅ 最终视频生成完成: {Path(output_video).name}")
            print(f"   文件路径: {output_video}")
            save_workflow_progress(DOWNLOAD_ROOT, "replace_audio", {
                "video_path": video_path,
                "output_video": str(output_video),
            })
        except Exception as e:
            print(f"\n❌ 替换音轨失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    elif not replace_video_audio:
        print("\n[5/6] 跳过视频音轨替换")
        print("=" * 60)
        print(f"✅ 音频文件已生成: {audio_path.name}")
    
    # 步骤6: 清理和总结
    print("\n[6/6] 流程完成总结...")
    print("=" * 60)
    
    # 检查生成的文件
    video_dir = video_path_obj.parent
    json_file = video_path_obj.with_suffix(".json")
    srt_file = video_path_obj.with_suffix(".srt")
    
    print(f"\n📁 输出文件：")
    if json_file.exists():
        print(f"  ✅ JSON字幕: {json_file.name}")
    if srt_file.exists():
        print(f"  ✅ SRT字幕: {srt_file.name}")
    if audio_path.exists():
        print(f"  ✅ 音频文件: {audio_path.name}")
    if replace_video_audio:
        output_video_path = video_path_obj.with_name(video_path_obj.stem + "_zh.mp4")
        if output_video_path.exists():
            print(f"  ✅ 最终视频: {output_video_path.name}")
    
    # 检查临时文件是否已清理
    tmp_dir = video_path_obj.with_name(video_path_obj.stem + "_tts_tmp")
    if tmp_dir.exists():
        print(f"\n⚠️  临时目录仍存在: {tmp_dir.name}（可手动删除）")
    else:
        print(f"\n✅ 临时文件已自动清理")
    
    # 清理进度文件（流程完成）
    clear_workflow_progress(DOWNLOAD_ROOT)
    
    return True


def main():
    """主程序入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        "完整工作流脚本",
        description="从YouTube下载到最终视频生成的完整流程"
    )
    
    parser.add_argument("url", nargs="?", type=str, help="YouTube视频URL（如果为空则交互式输入）")
    parser.add_argument("--no-asr-compare", action="store_true", help="不使用ASR对比（使用原始VTT）")
    parser.add_argument("--whisper-model", type=str, default="small", 
                       choices=["tiny", "base", "small", "medium", "large"],
                       help="Whisper模型大小（默认: small）")
    parser.add_argument("--no-weight-filter", action="store_true", help="禁用权重筛选")
    parser.add_argument("--min-weight", type=float, default=0.4,
                       help="最小权重阈值（默认: 0.4）")
    parser.add_argument("--no-translate", action="store_true", help="不翻译（保持原文）")
    parser.add_argument("--language", type=str, default="zh", help="目标语言（默认: zh）")
    parser.add_argument("--ai-rewrite", action="store_true", help="启用AI改写（注意：效果可能不理想）")
    parser.add_argument("--model-path", type=str, help="AI改写模型路径（启用 --ai-rewrite 时必需）")
    parser.add_argument("--no-replace", action="store_true", help="不替换视频音轨（只生成音频）")
    parser.add_argument("--bgm", type=str, default=None, help="纯音乐 BGM 文件路径（原视频仅人声时使用）")
    parser.add_argument("--bgm-volume", type=float, default=0.25, help="BGM 音量 0.0–1.0（默认 0.25）")
    parser.add_argument("--voice", type=str, default="zh-CN-XiaoxiaoNeural", help="TTS 语音（默认: zh-CN-XiaoxiaoNeural）")
    
    args = parser.parse_args()
    
    # 获取URL
    if args.url:
        url = args.url
    else:
        url = input("\n请输入 YouTube 视频 URL：").strip()
    
    if not url:
        print("❌ 未提供URL")
        parser.print_help()
        sys.exit(1)
    
    # 执行工作流
    success = complete_workflow(
        url=url,
        use_asr_compare=not args.no_asr_compare,
        whisper_model=args.whisper_model,
        enable_weight_filter=not args.no_weight_filter,
        min_weight=args.min_weight,
        translate=not args.no_translate,
        language=args.language,
        use_ai_rewrite=args.ai_rewrite,
        model_path=args.model_path,
        replace_video_audio=not args.no_replace,
        bgm_path=args.bgm,
        bgm_volume=args.bgm_volume,
        voice=args.voice,
    )
    
    if success:
        print("\n" + "=" * 60)
        print("🎉 完整工作流执行成功！")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ 工作流执行失败")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
