import json, os

d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'download')
for f in os.listdir(d):
    if 'asr_cache' in f:
        data = json.load(open(os.path.join(d, f), encoding='utf-8'))
        if isinstance(data, list):
            print(f'ASR cache: {len(data)} segments')
            for s in data[:10]:
                print(f'  [{s.get("start","?")} - {s.get("end","?")}] {repr(s.get("text",""))[:60]}')
        elif isinstance(data, dict):
            print('ASR cache keys:', list(data.keys())[:5])
        break

# Also check translated json
for f in os.listdir(d):
    if f.endswith('.json') and 'asr' not in f:
        data = json.load(open(os.path.join(d, f), encoding='utf-8'))
        if isinstance(data, list):
            print(f'\nTranslated: {len(data)} segments')
            for s in data[:10]:
                print(f'  [{s.get("start","?")} - {s.get("end","?")}] {repr(s.get("text",""))[:60]}')
        break
