# subtitle/video.py
"""
视频音轨替换与背景音乐处理：
- 原视频有背景音乐 + 人声 → 保留原背景音乐（压低） + AI 配音
- 原视频仅人声（无 BGM）→ 可指定纯音乐文件或使用默认 BGM，与 AI 配音混合
"""
from pathlib import Path
import os
import re
import subprocess
import imageio_ffmpeg

# 未指定 --bgm 时，若设置环境变量 SUBTITLE_DEFAULT_BGM，则自动使用该文件作为 BGM（原视频无背景时）
DEFAULT_BGM_ENV = "SUBTITLE_DEFAULT_BGM"


def _get_media_duration_seconds(media_path: str | Path) -> float:
    """获取音/视频时长（秒），优先 ffprobe，否则用 ffmpeg 解析 stderr"""
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    p = Path(ffmpeg_exe)
    ffprobe = str(p.with_name("ffprobe.exe" if p.name.lower() == "ffmpeg.exe" else "ffprobe"))
    cmd = [
        ffprobe, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(media_path)
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return float(out.stdout.strip())
    except Exception:
        pass
    # 无 ffprobe 时用 ffmpeg -i 从 stderr 解析 Duration
    try:
        out = subprocess.run(
            [ffmpeg_exe, "-i", str(media_path), "-f", "null", "-"],
            capture_output=True, text=True, timeout=15
        )
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", (out.stderr or ""))
        if m:
            h, m, s, cs = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            return h * 3600 + m * 60 + s + cs / 100.0
    except Exception:
        pass
    return 0.0


def replace_audio_in_video(
    video_path: Path,
    audio_path: str,
    preserve_background: bool = True,
    background_volume: float = 0.3,
    bgm_path: str | Path | None = None,
    bgm_volume: float = 0.25,
    default_bgm_path: str | Path | None = None,
) -> str:
    """
    替换视频音轨，支持两种背景处理方式：
    1) 原视频有背景音乐：保留原音轨（压低）与 AI 配音混合。
    2) 原视频仅人声：传入 bgm_path 或 default_bgm_path，用纯音乐（循环至视频长度）与 AI 配音混合。
    
    Args:
        video_path: 视频文件路径
        audio_path: 新音频文件路径（TTS 生成的音频）
        preserve_background: 是否保留/使用背景（原音轨或 BGM 文件）
        background_volume: 原视频背景音量（0.0–1.0），仅当未使用 BGM 文件时生效
        bgm_path: 纯音乐文件路径；若指定则用该 BGM 与 TTS 混合
        bgm_volume: BGM 文件音量（0.0–1.0）
        default_bgm_path: 未指定 bgm_path 时使用的默认 BGM（如环境变量 SUBTITLE_DEFAULT_BGM）；有则与 TTS 混合，不再使用原视频音轨
    
    Returns:
        生成视频的文件路径
    """
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    output_path = video_path.with_name(video_path.stem + "_zh.mp4")
    audio_path = str(audio_path)
    video_path = Path(video_path)
    # 优先用户指定的 BGM，其次默认 BGM：传入参数 → 环境变量 → 项目 assets/default_bgm.mp3
    effective_bgm: Path | None = Path(bgm_path) if bgm_path else None
    if not effective_bgm and default_bgm_path and Path(default_bgm_path).exists():
        effective_bgm = Path(default_bgm_path)
    if not effective_bgm and os.environ.get(DEFAULT_BGM_ENV):
        p = Path(os.environ[DEFAULT_BGM_ENV])
        if p.exists():
            effective_bgm = p
    if not effective_bgm:
        project_default = Path(__file__).resolve().parent.parent / "assets" / "default_bgm.mp3"
        if project_default.exists():
            effective_bgm = project_default

    # ---------- 模式：使用纯音乐 BGM（用户指定或默认 BGM）----------
    if effective_bgm and effective_bgm.exists():
        bgm_path = effective_bgm
        print(f"[Video] 使用纯音乐 BGM 模式：{Path(bgm_path).name}，音量 {int(bgm_volume * 100)}%")
        duration = _get_media_duration_seconds(audio_path) or _get_media_duration_seconds(video_path)
        if duration <= 0:
            print("[Warning] 无法获取时长，BGM 按 TTS 长度混合")
            duration = 300.0  # 默认 5 分钟
        duration_sec = int(duration) + 1
        bgm_duration = _get_media_duration_seconds(bgm_path)
        # BGM 大于视频 → 只截断；BGM 小于视频 → 循环到够长再截断
        need_loop = bgm_duration <= 0 or bgm_duration < duration_sec
        mixed_audio = video_path.with_suffix(".mixed_bgm_temp.wav")
        bgm_trimmed = video_path.with_suffix(".bgm_trimmed_temp.wav")
        timeout_seconds = max(1800, duration_sec * 3)
        try:
            # 步骤 1：生成与视频等长的 BGM 轨（截断或循环+截断）
            if need_loop:
                print(f"[Video] BGM 短于视频，循环后截断至 {duration_sec} 秒...")
                trim_cmd = [
                    ffmpeg_exe, "-y",
                    "-stream_loop", "-1", "-i", str(bgm_path),
                    "-t", str(duration_sec), "-ac", "2", "-ar", "44100",
                    str(bgm_trimmed)
                ]
            else:
                print(f"[Video] BGM 长于视频，截断至 {duration_sec} 秒...")
                trim_cmd = [
                    ffmpeg_exe, "-y", "-i", str(bgm_path),
                    "-t", str(duration_sec), "-ac", "2", "-ar", "44100",
                    str(bgm_trimmed)
                ]
            subprocess.run(trim_cmd, check=True, capture_output=True, timeout=timeout_seconds)
            # 步骤 2：BGM 与 TTS 混音（无循环，速度快）
            print(f"[Video] 混音 BGM + TTS...")
            mix_cmd = [
                ffmpeg_exe, "-y",
                "-i", str(bgm_trimmed), "-i", audio_path,
                "-filter_complex",
                f"[0:a]volume={bgm_volume}[bg];[1:a]volume=1.0[tts];[bg][tts]amix=inputs=2:duration=first:dropout_transition=2",
                "-ac", "2", "-ar", "44100",
                str(mixed_audio)
            ]
            subprocess.run(mix_cmd, check=True, capture_output=True, timeout=timeout_seconds)
            if bgm_trimmed.exists():
                bgm_trimmed.unlink()
            replace_cmd = [
                ffmpeg_exe, "-y", "-i", str(video_path), "-i", str(mixed_audio),
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-map", "0:v:0", "-map", "1:a:0", "-shortest", str(output_path)
            ]
            subprocess.run(replace_cmd, check=True)
            if mixed_audio.exists():
                mixed_audio.unlink()
            print(f"[Video] 视频生成完成（TTS + 纯音乐 BGM）")
            return str(output_path)
        except subprocess.TimeoutExpired:
            print(f"[Warning] BGM 处理超时（{timeout_seconds} 秒），改为仅 TTS")
        except subprocess.CalledProcessError as e:
            print(f"[Warning] BGM 混合失败: {e.stderr.decode() if e.stderr else e}，改为仅 TTS")
        if bgm_trimmed.exists():
            bgm_trimmed.unlink(missing_ok=True)
        if mixed_audio.exists():
            mixed_audio.unlink(missing_ok=True)

    # ---------- 模式：保留原视频背景音乐 ----------
    if preserve_background:
        print(f"[Video] 保留背景音乐模式：原音频音量 {int(background_volume * 100)}%")
        
        # 1. 提取原视频音频
        original_audio = video_path.with_suffix(".original_audio_temp.wav")
        extract_cmd = [
            ffmpeg_exe, "-y",
            "-i", str(video_path),
            "-vn",  # 不包含视频
            "-acodec", "pcm_s16le",  # PCM编码
            "-ar", "44100",  # 采样率
            "-ac", "2",  # 立体声
            str(original_audio)
        ]
        try:
            subprocess.run(extract_cmd, check=True, capture_output=True)
            print(f"[Video] 原视频音频已提取")
        except subprocess.CalledProcessError as e:
            print(f"[Warning] 提取原音频失败: {e.stderr.decode() if e.stderr else e}")
            # 如果提取失败，降级到直接替换模式
            preserve_background = False
        
        if preserve_background:
            # 2. 混合音频：降低原音频音量，叠加新TTS音频
            mixed_audio = video_path.with_suffix(".mixed_audio_temp.wav")
            mix_cmd = [
                ffmpeg_exe, "-y",
                "-i", str(original_audio),
                "-i", str(audio_path),
                "-filter_complex",
                f"[0:a]volume={background_volume}[bg];[1:a]volume=1.0[tts];[bg][tts]amix=inputs=2:duration=first:dropout_transition=2",
                str(mixed_audio)
            ]
            try:
                subprocess.run(mix_cmd, check=True, capture_output=True)
                print(f"[Video] 音频混合完成")
                
                # 3. 替换视频音轨（使用混合后的音频）
                replace_cmd = [
                    ffmpeg_exe, "-y",
                    "-i", str(video_path),
                    "-i", str(mixed_audio),
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "192k",  # 音频比特率
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-shortest",  # 以最短的流为准
                    str(output_path)
                ]
                subprocess.run(replace_cmd, check=True)
                
                # 清理临时文件
                if original_audio.exists():
                    original_audio.unlink()
                if mixed_audio.exists():
                    mixed_audio.unlink()
                
                print(f"[Video] 视频生成完成（已保留背景音乐）")
                return str(output_path)
            except subprocess.CalledProcessError as e:
                print(f"[Warning] 音频混合失败: {e.stderr.decode() if e.stderr else e}")
                # 如果混合失败，降级到直接替换模式
                preserve_background = False
                # 清理可能已生成的临时文件
                if original_audio.exists():
                    original_audio.unlink()
    
    # 降级模式：直接替换音轨（不保留背景音乐）
    if not preserve_background:
        print(f"[Video] 直接替换音轨模式（不保留背景音乐）")
        cmd = [
            ffmpeg_exe, "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            str(output_path)
        ]
        subprocess.run(cmd, check=True)
        print(f"[Video] 视频生成完成（直接替换）")
    
    return str(output_path)
