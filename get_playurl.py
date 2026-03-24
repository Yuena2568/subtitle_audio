import requests, json, os, subprocess
import http.cookiejar

bvid = 'BV1wR4y1G7AN'
cid = 478225372

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Referer': f'https://www.bilibili.com/video/{bvid}',
}

# 读 cookies from file
cookies = {}
with open('cookies.txt', 'r') as f:
    for line in f:
        if line.startswith('#') or not line.strip():
            continue
        parts = line.strip().split('\t')
        if len(parts) >= 7:
            cookies[parts[5]] = parts[6]

print(f'Cookies loaded: {len(cookies)}')
for k in cookies:
    print(f'  {k}: {cookies[k][:20]}...')

# 获取播放地址
play_url = f'https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=80&fnval=16&fourk=1'
resp = requests.get(play_url, headers=headers, cookies=cookies)
data = resp.json()
print(f'\nPlay URL API code: {data.get("code")}')

if data.get('code') == 0:
    durl = data['data'].get('durl', [])
    dash = data['data'].get('dash', [])
    if durl:
        print(f'Direct URL: {durl[0]["url"][:100]}...')
        video_url = durl[0]['url']
    elif dash:
        # DASH format - get best video + audio
        videos = sorted(dash.get('video', []), key=lambda x: x.get('bandwidth', 0), reverse=True)
        audios = sorted(dash.get('audio', []), key=lambda x: x.get('bandwidth', 0), reverse=True)
        if videos:
            print(f'Best video: {videos[0]["id"]} ({videos[0]["codecs"]}) {videos[0]["bandwidth"]}bps')
            video_url = videos[0]['baseUrl']
            print(f'Video URL: {video_url[:100]}...')
        if audios:
            print(f'Best audio: {audios[0]["id"]} ({audios[0]["codecs"]}) {audios[0]["bandwidth"]}bps')
            audio_url = audios[0]['baseUrl']
            print(f'Audio URL: {audio_url[:100]}...')
else:
    print(f'Error: {data}')
