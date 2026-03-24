with open('cookies.txt', 'r') as f:
    for i, line in enumerate(f):
        if line.startswith('#') or not line.strip():
            continue
        parts = line.strip().split('\t')
        name = parts[5] if len(parts) > 5 else '?'
        val_len = len(parts[6]) if len(parts) > 6 else 0
        print(f'Line {i}: {len(parts)} tabs, name={name}, val_len={val_len}')
