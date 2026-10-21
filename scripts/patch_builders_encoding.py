for fname in ['scripts/build_nro.py', 'scripts/build_nro_after_dark.py']:
    with open(fname, 'r', encoding='utf-8') as f:
        c = f.read()
    c = c.replace('capture_output=True, text=True', "capture_output=True, text=True, encoding='utf-8', errors='replace'")
    with open(fname, 'w', encoding='utf-8') as f:
        f.write(c)
    print(f'[OK] Patched {fname}')
