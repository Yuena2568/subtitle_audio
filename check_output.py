import os, json

d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'download')
for f in os.listdir(d):
    if f.endswith('.json') and 'asr' not in f:
        data = json.load(open(os.path.join(d, f), encoding='utf-8'))
        if isinstance(data, list):
            print(f"=== {f} ({len(data)} segments) ===")
            for s in data[:20]:
                start = s.get('start', '?')
                end = s.get('end', '?')
                text = s.get('text', '')[:80]
                # Also show zh if available
                zh = s.get('zh', s.get('translation', ''))
                zh_str = f" | zh: {zh[:60]}" if zh else ""
                print(f"  [{start} - {end}] {text}{zh_str}")
        break
