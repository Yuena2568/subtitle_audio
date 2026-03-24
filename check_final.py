import json, os

d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'download')
for f in os.listdir(d):
    if f.endswith('.json') and 'asr' not in f and 'translate' not in f and 'workflow' not in f:
        data = json.load(open(os.path.join(d, f), encoding='utf-8'))
        if isinstance(data, list):
            print(f'=== {len(data)} segments ===')
            for s in data[:15]:
                start = s.get('start', '?')
                end = s.get('end', '?')
                text = s.get('text', '')[:60]
                print(f'  [{start:.3f} - {end:.3f}] {text}')
            print('...')
            # Check if timestamps are realistic (not all integers)
            non_int = sum(1 for s in data if float(s.get('start', 0)) != int(float(s.get('start', 0))))
            print(f'Segments with non-integer start: {non_int}/{len(data)}')
        break
