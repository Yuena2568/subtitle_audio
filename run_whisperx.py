"""
使用 WhisperX 重新做 ASR，获取精确的单词级时间戳
"""
import os, sys, json
import whisperx

# 配置
AUDIO_PATH = None
VIDEO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'download')

# 找到 wav 文件
for f in os.listdir(VIDEO_DIR):
    if f.endswith('.wav'):
        AUDIO_PATH = os.path.join(VIDEO_DIR, f)
        break

assert AUDIO_PATH, "No WAV file found"
print(f"Audio: {AUDIO_PATH}")

# 1. 加载模型 + 转写
device = "cpu"
compute_type = "int8"  # CPU 上用 int8 最快

print("[1/3] Loading WhisperX model (medium)...")
model = whisperx.load_model("medium", device, compute_type=compute_type, language="en")

print("[2/3] Transcribing...")
result = model.transcribe(AUDIO_PATH, batch_size=4)
print(f"  Detected language: {result.get('language', '?')}")
print(f"  Segments: {len(result['segments'])}")

# 2. 强制对齐（获取单词级时间戳）
print("[3/3] Aligning with wav2vec2...")
model_a, metadata = whisperx.load_align_model(language_code="en", device=device)
result = whisperx.align(result["segments"], model_a, metadata, AUDIO_PATH, device)

# 3. 输出结果
segments = result["segments"]
print(f"\n=== WhisperX Result: {len(segments)} segments ===")
for s in segments[:15]:
    words_info = ""
    if "words" in s:
        words_info = f"  (words: {len(s['words'])})"
    print(f"  [{s['start']:.3f} - {s['end']:.3f}] {s['text'][:80]}{words_info}")

print("...")

# 保存到 ASR 缓存格式
cache_data = {
    "whisper_model": "whisperx-medium",
    "segment_count": len(segments),
    "segments": [
        {
            "index": i + 1,
            "start": round(s["start"], 3),
            "end": round(s["end"], 3),
            "text": s["text"].strip(),
            "words": s.get("words", [])
        }
        for i, s in enumerate(segments)
    ]
}

cache_file = os.path.join(VIDEO_DIR, [f for f in os.listdir(VIDEO_DIR) if f.endswith('.mp4')][0])
cache_file = os.path.splitext(cache_file)[0] + ".asr_cache.json"
with open(cache_file, "w", encoding="utf-8") as f:
    json.dump(cache_data, f, ensure_ascii=False, indent=2)
print(f"\nCache saved: {cache_file}")
print(f"Done! {len(segments)} segments with word-level timestamps.")
