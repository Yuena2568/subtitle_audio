import yt_dlp
import os
from datetime import datetime
import subprocess
import time
import imageio_ffmpeg
import pysrt
import json
import re

# ================================
# 配置区
# ================================
# 下载根目录：默认为项目根目录下的 download 文件夹
# 可以通过环境变量 SUBTITLE_DOWNLOAD_ROOT 自定义
DOWNLOAD_ROOT = os.getenv(
    "SUBTITLE_DOWNLOAD_ROOT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "download")
)
FFMPEG_BINARY = imageio_ffmpeg.get_ffmpeg_exe()
MAX_RETRY = 10  # 最大重试次数
GENERATE_JSON = True  # 是否生成字幕 JSON
MAX_HEIGHT = 1080  # 最大下载分辨率，避免 AV1

# ================================
# 文件名清理
# ================================
def sanitize_filename(name):
    # Windows 不允许 <>:"/\|?* 这些字符
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()

# ================================
# 下载进度显示
# ================================
def progress_hook(d):
    if d['status'] == 'downloading':
        total = d.get('total_bytes') or d.get('total_bytes_estimate')
        downloaded = d.get('downloaded_bytes', 0)
        if total:
            percent = downloaded / total * 100
            print(f"下载进度: {percent:.2f}%", end='\r')
    elif d['status'] == 'finished':
        print("下载完成                     ")

# ================================
# SRT 转 JSON
# ================================
def srt_to_json(srt_file, json_file):
    subs = pysrt.open(srt_file, encoding='utf-8')
    data = []
    for sub in subs:
        item = {
            "start": sub.start.ordinal / 1000.0,
            "end": sub.end.ordinal / 1000.0,
            "text": sub.text.replace('\n', ' ')
        }
        data.append(item)
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"字幕 JSON 已生成: {json_file}")

# ================================
# 合并字幕 JSON
# ================================
def merge_subtitle_jsons(bv_dir, mp4_files):
    merged_data = []
    total_offset = 0.0
    for mp4_file in mp4_files:
        json_file = mp4_file.replace('.mp4', '.json')
        if os.path.exists(json_file):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for item in data:
                item['start'] += total_offset
                item['end'] += total_offset
                merged_data.append(item)
            if data:
                total_offset = merged_data[-1]['end']
    merged_json_path = os.path.join(bv_dir, "merged_subtitles.json")
    if merged_data:
        with open(merged_json_path, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)
        print(f"多段字幕已合并成总 JSON: {merged_json_path}")
    return merged_json_path

# ================================
# 多视频无重新编码合并
# ================================
def concat_videos(bv_dir, mp4_files):
    if not mp4_files:
        print("没有找到 mp4 文件，无法合并")
        return None

    file_list_path = os.path.join(bv_dir, "file_list.txt")
    with open(file_list_path, 'w', encoding='utf-8') as f:
        for mp4 in mp4_files:
            f.write(f"file '{mp4}'\n")

    merged_video_path = os.path.join(bv_dir, "merged_video.mp4")

    cmd = [
        FFMPEG_BINARY,
        '-f', 'concat',
        '-safe', '0',
        '-i', file_list_path,
        '-c', 'copy',
        merged_video_path
    ]
    print("\n正在合并视频（无重新编码），请稍等...")
    subprocess.run(cmd, check=True)
    print(f"合并完成：{merged_video_path}")
    return merged_video_path

# ================================
# 单视频或播放列表下载
# ================================
def download_youtube_video(url):
    ydl_opts_info = {'quiet': True, 'skip_download': True}
    with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
        info = ydl.extract_info(url, download=False)

    video_list = info.get('entries', None)
    if video_list is None:
        video_list = [info]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = sanitize_filename(f"{info.get('title')}_{timestamp}")
    bv_dir = os.path.join(DOWNLOAD_ROOT, folder_name)
    os.makedirs(bv_dir, exist_ok=True)

    print(f"视频标题：{info.get('title')}")
    print(f"共 {len(video_list)} 段视频")
    print(f"保存路径：{bv_dir}\n")

    mp4_files = []
    failed_list = []

    for idx, v_info in enumerate(video_list, start=1):
        title = sanitize_filename(v_info.get('title', f"video{idx}"))
        safe_title = f"{idx:02d}_{title}"
        outtmpl = os.path.join(bv_dir, f"{safe_title}.%(ext)s")

        # 优先使用 web_embedded/android 等客户端，减少 YouTube 403 概率（参见 yt-dlp wiki）
        ydl_opts_download = {
            'format': f'bestvideo[ext=mp4][vcodec!=av01][height<={MAX_HEIGHT}]+bestaudio[ext=m4a]/best',
            'merge_output_format': 'mp4',
            'outtmpl': outtmpl,
            'ffmpeg_location': FFMPEG_BINARY,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'progress_hooks': [progress_hook],
            # 尝试不同 player_client，避免单一客户端被 403
            'extractor_args': {'youtube': {'player_client': ['web_embedded', 'android', 'web']}},
        }

        success = False
        last_403 = False  # 若上次是 403，下次用更保守的格式重试
        for attempt in range(1, MAX_RETRY + 1):
            try:
                opts = dict(ydl_opts_download)
                # 若上次遇到 403，改用更保守的格式（有时能拿到不同 CDN/格式，避免 403）
                if last_403:
                    opts['format'] = 'bestvideo[height<=720][vcodec!=av01]+bestaudio/best[height<=720]/best'
                    print(f"[重试] 使用保守格式 (height<=720) 以避免 403")
                print(f"开始下载 {safe_title} （尝试 {attempt}/{MAX_RETRY}）")
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([v_info['webpage_url']])

                mp4_file = outtmpl.replace('%(ext)s', 'mp4')
                if not os.path.exists(mp4_file):
                    raise ValueError("视频格式被排除或下载失败（可能是 AV1）")

                mp4_files.append(mp4_file)
                print(f"{safe_title} 下载完成\n")

                if GENERATE_JSON:
                    srt_path = outtmpl.replace('%(ext)s', 'en.srt')
                    json_path = outtmpl.replace('%(ext)s', 'json')
                    if os.path.exists(srt_path):
                        srt_to_json(srt_path, json_path)

                success = True
                break
            except Exception as e:
                err_str = str(e)
                last_403 = "403" in err_str or "Forbidden" in err_str
                print(f"{safe_title} 下载失败: {e}")
                time.sleep(2)

        if not success:
            failed_list.append(f"{safe_title} （可能是 AV1 或其他问题）")

    if failed_list:
        failed_file = os.path.join(bv_dir, "failed_videos.txt")
        with open(failed_file, 'w', encoding='utf-8') as f:
            for line in failed_list:
                f.write(line + "\n")
        print(f"失败的视频已记录在 {failed_file}")

    # 合并视频
    merged_video_path = concat_videos(bv_dir, mp4_files)

    # 合并字幕
    if GENERATE_JSON:
        merge_subtitle_jsons(bv_dir, mp4_files)

    print(f"\n最终视频生成完成：{merged_video_path}")

# ================================
# 主程序入口
# ================================
if __name__ == "__main__":
    os.makedirs(DOWNLOAD_ROOT, exist_ok=True)
    print("使用内置 ffmpeg:", FFMPEG_BINARY)
    url_input = input("请输入 YouTube 视频或播放列表 URL：").strip()
    download_youtube_video(url_input)
