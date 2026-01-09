# subtitle/video.py
from pathlib import Path
import subprocess

def replace_audio_in_video(video_path: Path, audio_path: str) -> str:
    """
    使用 ffmpeg 替换视频音轨，返回生成视频路径
    """
    output_path = video_path.with_name(video_path.stem + "_zh.mp4")
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(video_path),
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        str(output_path)
    ]
    subprocess.run(cmd, check=True)
    return str(output_path)
