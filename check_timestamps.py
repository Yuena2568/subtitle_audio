import json, os

d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'download')
for f in os.listdir(d):
    if 'asr_cache' in f:
        data = json.load(open(os.path.join(d, f), encoding='utf-8'))
        segs = data.get('segments', [])
        print(f'ASR: {len(segs)} segments')
        # Show all segment durations and gaps
        for i, s in enumerate(segs[:30]):
            dur = s['end'] - s['start']
            gap = s['start'] - segs[i-1]['end'] if i > 0 else 0
            print(f'  #{i}: [{s["start"]:.3f}-{s["end"]:.3f}] dur={dur:.3f}s gap={gap:.3f}s  {s["text"][:60]}')
        print('...')
        # Check if all durations are exactly 2.0
        exact_2 = sum(1 for s in segs if abs((s['end'] - s['start']) - 2.0) < 0.01)
        print(f'Segments with ~2.0s duration: {exact_2}/{len(segs)}')
        break
