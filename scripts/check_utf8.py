with open("catalog/data/catalog.json", "rb") as f:
    raw_bytes = f.read()

print(f"File size: {len(raw_bytes)} bytes")

# Check UTF-8 decoding with strict error handler
try:
    decoded = raw_bytes.decode("utf-8")
    print("Strict UTF-8 decode: SUCCESS")
except UnicodeDecodeError as e:
    print(f"Strict UTF-8 decode: FAILED! {e}")

# Check for \ufffd replacement character in decoded text
if "\ufffd" in decoded:
    print("WARNING: Replacement character \\ufffd found in decoded text!")
    lines = decoded.splitlines()
    for idx, l in enumerate(lines):
        if "\ufffd" in l:
            print(f"Line {idx+1}: {l.strip()[:100]}")
