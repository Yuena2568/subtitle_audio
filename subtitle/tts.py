# subtitle/tts.py
from __future__ import annotations
import sys, time, subprocess
from pathlib import Path
from typing import List
from difflib import SequenceMatcher
from subtitle.model import Segment

# 可选依赖：pydub 用于音频处理
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    AudioSegment = None

# 可选依赖：speech_preprocess 用于 TTS 预处理
try:
    from subtitle.speech_preprocess import prepare_segments_for_tts, SpeechSegment
    SPEECH_PREPROCESS_AVAILABLE = True
except ImportError:
    SPEECH_PREPROCESS_AVAILABLE = False

# ================== CLI 即时朗读 ==================
def speak(text: str) -> None:
    if not text or not text.strip():
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["powershell", "-Command",
                 f'Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{text}")'
                 ],
                check=False,
            )
        else:
            print("[TTS] speak() only supported on Windows for now")
    except Exception as e:
        print(f"[TTS] speak failed: {e}")

def speak_segments(segments: List[Segment], pause: float = 0.25) -> None:
    for seg in segments:
        if seg.text:
            speak(seg.text)
            time.sleep(pause)

# ================== 辅助函数 ==================
def merge_duplicate_segments(segments: List[Segment], similarity_threshold: float = 0.9) -> List[Segment]:
    if not segments: return []
    merged = [segments[0]]
    for seg in segments[1:]:
        prev = merged[-1]
        similarity = SequenceMatcher(None, prev.text, seg.text).ratio()
        try:
            duration = float(seg.end) - float(seg.start)
        except:
            duration = 0.0
        if similarity >= similarity_threshold and duration < 0.5:
            continue
        merged.append(seg)
    return merged

def merge_short_segments(segments: List[Segment], min_duration: float = 0.5) -> List[Segment]:
    if not segments: return []
    merged = []
    buffer = segments[0]
    for seg in segments[1:]:
        try:
            duration = float(seg.end) - float(seg.start)
        except:
            duration = 0.0
        if duration < min_duration:
            buffer.text += " " + seg.text
            buffer.end = seg.end
        else:
            merged.append(buffer)
            buffer = seg
    merged.append(buffer)
    return merged

# ================== 语速贴合（按原视频时间轴） ==================
def _change_audio_speed(audio: "AudioSegment", speed_factor: float) -> "AudioSegment":
    """
    改变音频播放速度（不改变音高）。
    speed_factor > 1 加快，< 1 减慢；返回的时长 = 原时长 / speed_factor。
    """
    if not PYDUB_AVAILABLE or audio is None:
        return audio
    if abs(speed_factor - 1.0) < 0.02:
        return audio
    new_frame_rate = int(audio.frame_rate * speed_factor)
    # 通过改变 frame_rate 实现变速，时长 = 原时长 / speed_factor；不改回 frame_rate 以保证时长正确
    chunk = audio._spawn(audio.raw_data, overrides={"frame_rate": new_frame_rate})
    return chunk


# ================== Edge-TTS ==================
def _edge_tts_to_wav(text: str, wav_path: Path, voice: str = "zh-CN-XiaoxiaoNeural", rate: str = "+0%"):
    """
    使用 edge-tts 生成音频文件
    注意：edge-tts 默认生成 mp3 格式，但我们可以指定 wav 扩展名
    """
    if not text.strip(): 
        return
    
    # edge-tts 会根据扩展名生成对应格式，但实际可能生成 mp3
    # 所以我们先生成，然后如果需要可以转换
    cmd = ["edge-tts", "--voice", voice, "--rate", rate, "--text", text, "--write-media", str(wav_path)]
    try:
        result = subprocess.run(
            cmd, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.PIPE, 
            check=True,
            text=True
        )
        # 检查文件是否生成（edge-tts 可能生成 mp3 而不是 wav）
        if not wav_path.exists():
            # 尝试查找 mp3 文件
            mp3_path = wav_path.with_suffix(".mp3")
            if mp3_path.exists():
                # 如果生成了 mp3，转换为 wav（如果需要）
                if PYDUB_AVAILABLE:
                    audio = AudioSegment.from_file(str(mp3_path))
                    audio.export(str(wav_path), format="wav")
                    mp3_path.unlink()  # 删除 mp3 文件
    except subprocess.CalledProcessError as e:
        print(f"[TTS] edge-tts 生成失败: {e.stderr}")
        raise

# ================== 时间轴对齐检测 ==================
def detect_timeline_offset(segments: List[Segment]) -> float:
    """
    检测时间轴偏移量
    
    如果第一个segment的start时间很小（<2秒），但实际视频可能从更晚开始，
    通过分析segment时间间隔来检测偏移。
    
    Args:
        segments: Segment列表
    
    Returns:
        检测到的偏移量（秒），如果没有偏移则返回0.0
    """
    if not segments or len(segments) < 2:
        return 0.0
    
    first_seg_start = float(segments[0].start)
    
    # 如果第一个segment的start >= 2秒，认为时间轴正常
    if first_seg_start >= 2.0:
        return 0.0
    
    # 如果第一个segment的start < 2秒，检查是否有明显的时间间隔
    # 方法1: 检查第二个segment的start时间
    if len(segments) >= 2:
        second_seg_start = float(segments[1].start)
        gap = second_seg_start - first_seg_start
        
        # 如果前两个segment之间的gap > 10秒，说明第一个segment之前可能有长时间的静音
        # 这种情况下，第一个segment的时间戳可能是错误的
        # 但是，我们不能简单地假设有偏移，需要更谨慎的判断
        
        # 方法2: 分析所有segment之间的间隔分布
        gaps = []
        for i in range(1, min(len(segments), 10)):  # 只分析前10个segment
            prev_end = float(segments[i-1].end)
            curr_start = float(segments[i].start)
            gap = curr_start - prev_end
            if gap > 0:  # 只考虑正间隔
                gaps.append(gap)
        
        if gaps:
            avg_gap = sum(gaps) / len(gaps)
            # 如果第一个segment的start很小，但后续segment的平均间隔也正常
            # 且第一个segment和第二个segment之间有大的gap，说明可能有偏移
            
            # 如果第一个segment的start < 1秒，但第二个segment的start > 10秒
            # 说明第一个segment之前可能有10秒左右的静音
            if first_seg_start < 1.0 and second_seg_start > 10.0:
                # 检测第一个segment的实际位置：如果第二个segment的start很大，
                # 可能是第一个segment的时间戳不准确，实际应该在更晚的位置
                # 但这种情况比较复杂，我们先不自动修正，而是提醒用户
                print(f"[TTS] 检测到时间轴异常：第一个segment在 {first_seg_start:.2f}秒，第二个在 {second_seg_start:.2f}秒")
                print(f"[TTS] 如果第一个segment实际位置不在 {first_seg_start:.2f}秒，可能需要手动调整")
        
        # 更保守的方法：如果第一个segment的start < 0.5秒，但第二个segment的start很大
        # 且gap > 第一个segment的start的10倍，说明可能有明显的偏移
        if first_seg_start < 0.5 and gap > first_seg_start * 10:
            # 这种情况下，我们假设第一个segment的时间戳应该更接近第二个segment的时间
            # 但这可能不准确，所以我们先不自动修正，只返回0
            # 更安全的方法是：如果用户明确知道偏移量，应该通过参数传递
            pass
    
    return 0.0


def apply_timeline_offset(segments: List[Segment], offset: float) -> List[Segment]:
    """
    应用时间轴偏移量到所有segment
    
    Args:
        segments: Segment列表
        offset: 偏移量（秒），正数表示向后偏移
    
    Returns:
        调整后的Segment列表
    """
    if offset == 0.0:
        return segments
    
    adjusted = []
    for seg in segments:
        new_seg = Segment(
            index=seg.index,
            text=seg.text,
            start=float(seg.start) + offset,
            end=float(seg.end) + offset
        )
        adjusted.append(new_seg)
    
    return adjusted


def detect_actual_audio_start(video_path: str | Path, estimated_start: float) -> float:
    """
    检测视频实际音频开始时间
    
    通过分析视频音频的静音检测来找到实际有声音的开始时间
    
    Args:
        video_path: 视频文件路径
        estimated_start: 估计的开始时间（从segment获取）
    
    Returns:
        实际音频开始时间（秒）
    """
    try:
        import subprocess
        import imageio_ffmpeg
        
        # 使用 ffmpeg 的 silencedetect 滤镜来检测静音
        # 这会找出音频中非静音的部分
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        video_path_str = str(video_path)
        cmd = [
            ffmpeg_exe,
            "-i", video_path_str,
            "-af", "silencedetect=noise=-30dB:duration=0.5",
            "-f", "null",
            "-"
        ]
        result = subprocess.run(
            cmd,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30
        )
        
        # 解析 ffmpeg 输出，查找第一个非静音的时间点
        # silencedetect 输出格式: silence_start: 0.0 | silence_end: 12.0 | silence_duration: 12.0
        stderr = result.stderr
        lines = stderr.split('\n')
        
        # 查找第一个 silence_end，这表示静音结束，音频开始
        first_silence_end = None
        for line in lines:
            if 'silence_end' in line:
                # 解析: silence_end: 12.0
                parts = line.split('silence_end:')
                if len(parts) > 1:
                    try:
                        end_time = float(parts[1].strip().split()[0])
                        if first_silence_end is None or end_time < first_silence_end:
                            first_silence_end = end_time
                    except (ValueError, IndexError):
                        continue
        
        if first_silence_end is not None and first_silence_end > 1.0:
            # 如果检测到的开始时间 > 1秒，且与估计的开始时间差异较大，使用检测值
            if abs(first_silence_end - estimated_start) > 2.0:
                return first_silence_end
        
        # 如果没有检测到明显的静音结束点，返回估计值
        return estimated_start
        
    except Exception as e:
        # 如果检测失败，返回估计值
        return estimated_start

# ================== 时间轴 TTS ==================
def synthesize_audio_timeline(
    segments: List[Segment],
    output_path: str,
    voice: str = "zh-CN-XiaoxiaoNeural",
    video_path: str | None = None,
    match_speech_rate: bool = True,
) -> str:
    """
    生成时间轴对齐的音频。
    
    Args:
        segments: Segment 列表
        output_path: 输出音频文件路径
        voice: TTS 语音
        video_path: 视频路径（可选，用于检测实际音频开始时间）
        match_speech_rate: 是否按原视频每段时长贴合语速（逐句 TTS 后拉伸/压缩到原时长）
    """
    if not PYDUB_AVAILABLE:
        raise ImportError("pydub 模块未安装，TTS 功能不可用。请使用 pip install pydub 安装")
    if not SPEECH_PREPROCESS_AVAILABLE:
        raise ImportError("speech_preprocess 模块不可用，TTS 功能不可用")
    
    print("[TTS] Synthesizing timeline audio...")
    
    # 检测并修正时间轴偏移
    time_offset = detect_timeline_offset(segments)
    if time_offset != 0.0:
        print(f"[TTS] 检测到时间轴偏移: {time_offset:.2f}秒，已自动修正")
        segments = apply_timeline_offset(segments, time_offset)
    
    # 仅当第一个 segment 开始时间异常早（<0.3s）时才做“实际音频开始”检测，避免把正常字幕整体后移约 1 秒
    first_start = float(segments[0].start) if segments else 0.0
    if video_path and segments and first_start < 0.3:
        try:
            actual_start_time = detect_actual_audio_start(video_path, first_start)
            if actual_start_time > first_start:
                offset = actual_start_time - first_start
                if offset > 0.5:  # 仅当检测到明显偏移（>0.5s）才应用
                    print(f"[TTS] 检测到实际音频开始时间: {actual_start_time:.2f}秒，应用偏移: {offset:.2f}秒")
                    segments = apply_timeline_offset(segments, offset)
        except Exception as e:
            print(f"[TTS] 检测实际音频开始时间失败: {e}，使用 segment 时间戳")
    
    speech_segments: List[SpeechSegment] = prepare_segments_for_tts(segments)
    if not speech_segments: raise RuntimeError("[TTS] No segments after preprocessing")

    seg_list = [Segment(index=seg.index, start=float(seg.start), end=float(seg.end), text=seg.text) for seg in speech_segments]
    seg_list = merge_duplicate_segments(seg_list)
    seg_list = merge_short_segments(seg_list)
    if not seg_list: raise RuntimeError("[TTS] No segments after merge/cleanup")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = output_path.with_name(output_path.stem + "_tts_tmp")
    tmp_dir.mkdir(exist_ok=True)

    rendered: list[tuple[Segment, Path, int]] = []

    if match_speech_rate:
        # 语速贴合：逐句 TTS 用默认语速生成，整条时间轴做一次全局变速，避免每句语速不同
        print("[TTS] 语速贴合模式：逐句生成，整轨统一变速")
        for i, seg in enumerate(seg_list):
            seg_wav = tmp_dir / f"seg_{seg.index:04d}.wav"
            try:
                _edge_tts_to_wav(seg.text.strip(), seg_wav, voice=voice)
                audio = AudioSegment.from_file(str(seg_wav))
            except Exception as e:
                print(f"[TTS] 段落 {seg.index} 生成失败: {e}，使用静音")
                target_ms = max(1, int((seg.end - seg.start) * 1000))
                audio = AudioSegment.silent(duration=target_ms)
                audio.export(seg_wav, format="wav")
            # 不做单句拉伸，只记录原段时长用于时间轴放置
            target_ms = max(1, int((seg.end - seg.start) * 1000))
            rendered.append((seg, seg_wav, target_ms))
    else:
        batch_size = 5
        batch_text: List[str] = []
        batch_indices: List[int] = []

        def flush_batch():
            if not batch_text:
                return
            batch_content = " ".join(batch_text)
            batch_wav = tmp_dir / f"batch_{batch_indices[0]:04d}.wav"
            _edge_tts_to_wav(batch_content, batch_wav, voice=voice)
            try:
                audio_all = AudioSegment.from_file(str(batch_wav))
            except Exception as e:
                print(f"[TTS] Failed to load batch wav {batch_wav}: {e}")
                batch_text.clear()
                batch_indices.clear()
                return
            cursor_ms = 0
            for idx, seg_index in enumerate(batch_indices):
                seg = seg_list[seg_index]
                target_ms = max(1, int((seg.end - seg.start) * 1000))
                if len(audio_all) > cursor_ms:
                    audio_seg = audio_all[cursor_ms:cursor_ms + target_ms]
                    if len(audio_seg) < target_ms:
                        audio_seg += AudioSegment.silent(duration=target_ms - len(audio_seg))
                else:
                    audio_seg = AudioSegment.silent(duration=target_ms)
                seg_wav_path = tmp_dir / f"seg_{seg.index:04d}.wav"
                audio_seg.export(seg_wav_path, format="wav")
                rendered.append((seg, seg_wav_path, target_ms))
                cursor_ms += target_ms
            batch_text.clear()
            batch_indices.clear()

        for i, seg in enumerate(seg_list):
            batch_text.append(seg.text.strip())
            batch_indices.append(i)
            if len(batch_text) >= batch_size:
                flush_batch()
        flush_batch()

    if not rendered:
        raise RuntimeError("[TTS] No audio rendered")

    # 自然语速 + 智能错开：每句按自然语速播放，超出原时间窗口则顺移后续段落
    # 不拉伸、不压缩，保证语音质量自然
    print("[TTS] 自然语速模式：按原时间轴对齐，超出则顺移")

    # 第一遍：计算每段的实际播放位置（自然语速，不拉伸）
    GAP_MS = 80  # 段落间最小间隔（毫秒）
    placements = []  # [(start_ms, end_ms, wav_path), ...]
    cursor_ms = 0

    for seg, wav_path, orig_target_ms in rendered:
        if not wav_path.exists():
            continue
        try:
            audio = AudioSegment.from_file(str(wav_path))
        except Exception as e:
            print(f"[TTS] 加载段落 {seg.index} 失败: {e}，跳过")
            continue
        actual_ms = len(audio)

        # 原视频期望的开始位置
        desired_start = int(seg.start * 1000)

        # 实际开始位置 = max(光标位置, 原始时间轴位置)
        # 这样尽量贴近原时间轴，但不重叠
        actual_start = max(cursor_ms, desired_start)

        actual_end = actual_start + actual_ms
        placements.append((actual_start, actual_end, wav_path, audio))
        cursor_ms = actual_end + GAP_MS

    if not placements:
        raise RuntimeError("[TTS] No audio to place")

    # 第二遍：拼接时间轴
    total_ms = placements[-1][1] + 500  # 最后一段结束后多留 500ms
    timeline = AudioSegment.silent(duration=total_ms)

    for start_ms, end_ms, wav_path, audio in placements:
        timeline = timeline.overlay(audio, position=start_ms)

    # 裁掉尾部多余静音
    if len(timeline) > placements[-1][1] + 200:
        timeline = timeline[:placements[-1][1] + 200]

    if output_path.suffix.lower() != ".wav":
        output_path = output_path.with_suffix(".wav")
    timeline.export(output_path, format="wav")
    print(f"[TTS] Exported timeline audio -> {output_path}")
    
    # 清理临时文件
    import shutil
    if tmp_dir.exists():
        try:
            shutil.rmtree(tmp_dir)
            print(f"[TTS] 已清理临时目录: {tmp_dir}")
        except Exception as e:
            print(f"[Warning] 清理临时目录失败: {e}，可手动删除 {tmp_dir}")
    
    return str(output_path)
