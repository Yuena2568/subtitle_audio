import requests, json, os, subprocess, sys

bvid = 'BV1wR4y1G7AN'
cid = 478225372
download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'download')
os.makedirs(download_dir, exist_ok=True)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Referer': f'https://www.bilibili.com/video/{bvid}',
}

# Step 1: Get video info
print('Getting video info...')
api_url = f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}'
resp = requests.get(api_url, headers=headers)
data = resp.json()
assert data['code'] == 0, f"API error: {data}"
info = data['data']
title = info['title']
print(f'Title: {title}')
cid = info['pages'][0]['cid']
print(f'CID: {cid}')

# Step 2: Get play URL (try DASH first for best quality)
print('\nGetting play URL...')
play_url = f'https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=80&fnval=16&fourk=1'
resp = requests.get(play_url, headers=headers)
pdata = resp.json()
assert pdata['code'] == 0, f"Play URL error: {pdata}"

dash = pdata['data'].get('dash')
safe_title = "".join(c for c in title if c.isalnum() or c in ' _-').strip()

if dash:
    # DASH mode - separate video + audio
    videos = sorted(dash.get('video', []), key=lambda x: x.get('bandwidth', 0), reverse=True)
    audios = sorted(dash.get('audio', []), key=lambda x: x.get('bandwidth', 0), reverse=True)
    
    video_stream = videos[0]
    audio_stream = audios[0] if audios else None
    
    print(f'Video: {video_stream["width"]}x{video_stream["height"]} {video_stream["codecs"]} {video_stream["bandwidth"]}bps')
    if audio_stream:
        print(f'Audio: {audio_stream["codecs"]} {audio_stream["bandwidth"]}bps')
    
    # Download video
    video_path = os.path.join(download_dir, f'{safe_title}_video.m4s')
    audio_path = os.path.join(download_dir, f'{safe_title}_audio.m4s')
    output_path = os.path.join(download_dir, f'{safe_title}.mp4')
    
    print(f'\nDownloading video stream...')
    dl_headers = {**headers, 'Referer': f'https://www.bilibili.com/video/{bvid}'}
    r = requests.get(video_stream['baseUrl'], headers=dl_headers, stream=True)
    total = int(r.headers.get('content-length', 0))
    downloaded = 0
    with open(video_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded / total * 100
                print(f'  Video: {pct:.1f}% ({downloaded}/{total})', end='\r')
    print(f'\n  Video done: {downloaded} bytes')
    
    if audio_stream:
        print(f'Downloading audio stream...')
        r = requests.get(audio_stream['baseUrl'], headers=dl_headers, stream=True)
        total = int(r.headers.get('content-length', 0))
        downloaded = 0
        with open(audio_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f'  Audio: {pct:.1f}% ({downloaded}/{total})', end='\r')
        print(f'\n  Audio done: {downloaded} bytes')
    
    # Merge with ffmpeg
    print(f'\nMerging with ffmpeg...')
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    if audio_stream:
        cmd = [ffmpeg, '-y', '-i', video_path, '-i', audio_path, '-c:v', 'copy', '-c:a', 'copy', output_path]
    else:
        cmd = [ffmpeg, '-y', '-i', video_path, '-c', 'copy', output_path]
    subprocess.run(cmd, check=True, capture_output=True)
    
    # Cleanup
    os.remove(video_path)
    if audio_stream and os.path.exists(audio_path):
        os.remove(audio_path)
    
    print(f'\nDone! Output: {output_path}')
    
else:
    # Direct URL mode
    durl = pdata['data']['durl'][0]
    print(f'Direct URL: quality={pdata["data"]["quality"]}')
    output_path = os.path.join(download_dir, f'{safe_title}.mp4')
    
    print(f'Downloading...')
    dl_headers = {**headers, 'Referer': f'https://www.bilibili.com/video/{bvid}'}
    r = requests.get(durl['url'], headers=dl_headers, stream=True)
    total = int(r.headers.get('content-length', 0))
    downloaded = 0
    with open(output_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded / total * 100
                print(f'  {pct:.1f}% ({downloaded}/{total})', end='\r')
    print(f'\nDone! Output: {output_path}')
