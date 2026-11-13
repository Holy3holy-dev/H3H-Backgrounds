with open("scripts/expand_new_switch_titles.py", "r", encoding="utf-8") as f:
    text = f.read()

target = '"notes": f"Switch 720p 30fps H264 | {var_name[:40]}"\n        }'
replacement = '''"notes": f"Switch 720p 30fps H264 | {var_name[:40]}"
        }

        if icon_url:
            new_variant["hasIcon"] = True
            new_variant["iconUrl"] = icon_url
            new_variant["iconSizeBytes"] = icon_size
            new_variant["iconCodec"] = "h264"
            new_variant["iconWidth"] = 256
            new_variant["iconHeight"] = 256'''

if target in text:
    text = text.replace(target, replacement, 1)
    with open("scripts/expand_new_switch_titles.py", "w", encoding="utf-8") as f:
        f.write(text)
    print("Successfully patched with LF!")
else:
    target_crlf = '"notes": f"Switch 720p 30fps H264 | {var_name[:40]}"\r\n        }'
    replacement_crlf = '''"notes": f"Switch 720p 30fps H264 | {var_name[:40]}"\r\n        }\r\n\r\n        if icon_url:\r\n            new_variant["hasIcon"] = True\r\n            new_variant["iconUrl"] = icon_url\r\n            new_variant["iconSizeBytes"] = icon_size\r\n            new_variant["iconCodec"] = "h264"\r\n            new_variant["iconWidth"] = 256\r\n            new_variant["iconHeight"] = 256'''
    if target_crlf in text:
        text = text.replace(target_crlf, replacement_crlf, 1)
        with open("scripts/expand_new_switch_titles.py", "w", encoding="utf-8") as f:
            f.write(text)
        print("Successfully patched with CRLF!")
    else:
        print("Target pattern not found")
