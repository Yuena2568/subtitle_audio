# subtitle/asr.py
from pathlib import Path
import subprocess
from typing import List
from subtitle.model import Segment

def extract_audio(video_path: str, audio_path: str):
    """
    从视频文件中提取音频，保存为 wav 文件（16k 单声道）
    """
    video_path = Path(video_path)
    audio_path = Path(audio_path)
    audio_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",             # 覆盖输出文件
        "-i", str(video_path),
        "-vn",            # 不要视频流
        "-acodec", "pcm_s16le",  # wav 编码
        "-ar", "16000",   # 采样率 16k
        "-ac", "1",       # 单声道
        str(audio_path)
    ]
    try:
        subprocess.run(cmd, check=True)
        print(f"[ASR] Audio extracted: {audio_path}")
    except Exception as e:
        print(f"[ASR] Audio extraction failed: {e}")
        raise

def audio_to_segments(audio_path: str, model_size: str = "small") -> List[Segment]:
    """
    使用本地 ASR 模型，将音频转换为 Segment 列表
    
    Args:
        audio_path: 音频文件路径
        model_size: Whisper 模型大小（tiny/base/small/medium/large），默认 "small"
    
    Returns:
        Segment 列表
    """
    try:
        from whisper import load_model  # pip install openai-whisper
    except ImportError:
        raise ImportError(
            "whisper 模块未安装。请使用 uv add openai-whisper 安装。"
            "如果不需要 ASR 功能，可以使用现有的 VTT/SRT 字幕文件。"
        )

    try:
        print(f"[ASR] 加载 Whisper 模型: {model_size}...")
        model = load_model(model_size)  # 你可以选择 tiny/base/small/medium/large
        print(f"[ASR] 开始转写音频: {audio_path}")
        result = model.transcribe(audio_path)

        segments = []
        for i, seg in enumerate(result["segments"]):
            # 确保 start 和 end 是 float 类型
            segment = Segment(
                index=i + 1,
                start=float(seg["start"]),
                end=float(seg["end"]),
                text=seg["text"].strip()
            )
            segments.append(segment)
        print(f"[ASR] {len(segments)} segments generated from audio")
        return segments
    except Exception as e:
        raise RuntimeError(f"ASR 转写失败: {e}")
