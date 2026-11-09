from pathlib import Path

p = Path("studio/h3h_studio/core/express_processor.py")
content = p.read_text(encoding="utf-8")

if "publish_to_cloud" not in content:
    old = '            "push_ok": push_ok\n        }'
    new = '            "push_ok": push_ok\n        }\n\n    # Backward compatibility alias\n    publish_to_cloud = publish_community_asset'
    assert old in content, "Target block not found"
    content = content.replace(old, new)
    p.write_text(content, encoding="utf-8")
    print("[+] Added publish_to_cloud alias to ExpressProcessor")
else:
    print("[*] publish_to_cloud already in express_processor.py")
