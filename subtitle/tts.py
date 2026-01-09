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

# ================== 时间轴 TTS ==================
def synthesize_audio_timeline(segments: List[Segment], output_path: str, voice: str = "zh-CN-XiaoxiaoNeural") -> str:
    if not PYDUB_AVAILABLE:
        raise ImportError("pydub 模块未安装，TTS 功能不可用。请使用 pip install pydub 安装")
    if not SPEECH_PREPROCESS_AVAILABLE:
        raise ImportError("speech_preprocess 模块不可用，TTS 功能不可用")
    
    print("[TTS] Synthesizing timeline audio...")
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
    batch_size = 5
    batch_text: List[str] = []
    batch_indices: List[int] = []

    def flush_batch():
        if not batch_text: return
        batch_content = " ".join(batch_text)
        batch_wav = tmp_dir / f"batch_{batch_indices[0]:04d}.wav"
        _edge_tts_to_wav(batch_content, batch_wav, voice=voice)

        try:
            # edge-tts 生成的文件可能是 mp3 格式，使用 from_file 自动检测
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
        if len(batch_text) >= batch_size: flush_batch()
    flush_batch()

    if not rendered: raise RuntimeError("[TTS] No audio rendered")

    timeline = AudioSegment.silent(duration=0)
    cursor_ms = 0
    for seg, wav_path, target_ms in rendered:
        if not wav_path.exists(): continue
        start_ms = int(seg.start * 1000)
        if start_ms > cursor_ms:
            timeline += AudioSegment.silent(duration=start_ms - cursor_ms)
            cursor_ms = start_ms
        try:
            # 使用 from_file 自动检测文件格式（edge-tts 可能生成 mp3）
            audio = AudioSegment.from_file(str(wav_path))
        except Exception as e:
            print(f"[TTS] Failed to load segment audio {wav_path}: {e}")
            # 如果加载失败，使用静音填充
            audio = AudioSegment.silent(duration=target_ms)
        if len(audio) > target_ms: audio = audio[:target_ms]
        elif len(audio) < target_ms: audio += AudioSegment.silent(duration=target_ms - len(audio))
        timeline += audio
        cursor_ms += len(audio)

    if output_path.suffix.lower() != ".wav": output_path = output_path.with_suffix(".wav")
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
