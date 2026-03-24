import yt_dlp

url = 'https://www.bilibili.com/video/BV1wR4y1G7AN'
ydl_opts = {
    'quiet': True,
    'skip_download': True,
    'cookiesfrombrowser': ('edge',),
}
ydl = yt_dlp.YoutubeDL(ydl_opts)
info = ydl.extract_info(url, download=False)
print('Title:', info.get('title'))
entries = info.get('entries', [info])
print('Parts:', len(entries))
for i, e in enumerate(entries, 1):
    title = e.get('title', '?')
    print(f'  P{i}: {title}')
