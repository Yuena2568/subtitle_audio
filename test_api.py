import requests, re, json

bvid = 'BV1wR4y1G7AN'

# B站 API 获取视频信息
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Referer': 'https://www.bilibili.com/',
    'Origin': 'https://www.bilibili.com',
}

# 读 cookies
cookies = {}
with open('cookies.txt', 'r') as f:
    for line in f:
        if line.startswith('#') or not line.strip():
            continue
        parts = line.strip().split('\t')
        if len(parts) >= 7:
            cookies[parts[5]] = parts[6]

print(f'Cookies: {len(cookies)}')

# 先试 API
api_url = f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}'
resp = requests.get(api_url, headers=headers, cookies=cookies)
print(f'API status: {resp.status_code}')
data = resp.json()
if data.get('code') == 0:
    info = data['data']
    print(f'Title: {info["title"]}')
    print(f'Pages: {len(info.get("pages", []))}')
    for p in info.get('pages', []):
        print(f'  P{p["page"]}: {p["part"]} (cid={p["cid"]})')
else:
    print(f'API error: {data}')
