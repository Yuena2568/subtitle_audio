import json, os

d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'download')
for f in os.listdir(d):
    if 'asr_cache' in f:
        data = json.load(open(os.path.join(d, f), encoding='utf-8'))
        segs = data.get('segments', [])
        print(f'ASR: {len(segs)} segments, model={data.get("whisper_model")}')
        for s in segs[:10]:
            print(f'  [{s.get("start","?")} - {s.get("end","?")}] {repr(s.get("text",""))[:80]}')
        print('...')
        # show a few from the middle
        if len(segs) > 20:
            for s in segs[20:25]:
                print(f'  [{s.get("start","?")} - {s.get("end","?")}] {repr(s.get("text",""))[:80]}')
        break

# Now check translated json for comparison
for f in os.listdir(d):
    if f.endswith('.json') and 'asr' not in f:
        data = json.load(open(os.path.join(d, f), encoding='utf-8'))
        print(f'\nTranslated: {len(data)} segments')
        for s in data[20:25]:
            print(f'  [{s.get("start","?")} - {s.get("end","?")}] {repr(s.get("text",""))[:80]}')
        break
