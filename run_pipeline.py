import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import process_single_file

# 找到下载的视频
download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'download')
mp4_files = [f for f in os.listdir(download_dir) if f.endswith('.mp4')]
assert mp4_files, "No mp4 file found in download/"
video_path = os.path.join(download_dir, mp4_files[0])
print(f"Video: {video_path}")
print(f"Size: {os.path.getsize(video_path) / 1024 / 1024:.1f} MB")

# 运行完整流程: ASR → 翻译 → 导出字幕 → TTS → 替换音轨
process_single_file(
    video_path,
    translate=True,
    tts=True,
    export=True,
    video_replace=video_path,
    use_asr_compare=True,
    whisper_model="whisperx-medium",
    language="zh",
    match_speech_rate=True,
    voice="zh-CN-XiaoxiaoNeural",
)
