for fname in ['scripts/build_nro.py', 'scripts/build_nro_after_dark.py']:
    with open(fname, 'r', encoding='utf-8') as f:
        c = f.read()
    c = c.replace('print(res.stderr)', "print(res.stderr.encode('ascii', errors='replace').decode('ascii'))")
    with open(fname, 'w', encoding='utf-8') as f:
        f.write(c)
    print(f'[OK] Safe stderr in {fname}')
