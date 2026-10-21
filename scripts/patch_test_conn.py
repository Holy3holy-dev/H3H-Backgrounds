from pathlib import Path

p = Path("studio/h3h_studio/core/google_drive.py")
text = p.read_text(encoding="utf-8")

old_snippet = '''        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            user_data = data.get("user", {})
            quota_data = data.get("storageQuota", {})
            limit = int(quota_data.get("limit", 0))
            usage = int(quota_data.get("usage", 0))
            limit_gb = limit / (1024 ** 3)
            usage_gb = usage / (1024 ** 3)
            free_gb = max(0.0, limit_gb - usage_gb) if limit > 0 else 0.0
            quota_str = f"Занято {usage_gb:.1f} ГБ из {limit_gb:.1f} ГБ (свободно {free_gb:.1f} ГБ)" if limit > 0 else f"Занято {usage_gb:.1f} ГБ"
            return {
                "success": True,
                "ok": True,
                "user": user_data.get("displayName", "Google User"),
                "displayName": user_data.get("displayName", "Google User"),
                "email": user_data.get("emailAddress", ""),
                "emailAddress": user_data.get("emailAddress", ""),
                "limit": limit,
                "limit_gb": limit_gb,
                "usage": usage,
                "usage_gb": usage_gb,
                "usageInDrive": int(quota_data.get("usageInDrive", 0)),
                "free": max(0, limit - usage) if limit > 0 else 0,
                "free_gb": free_gb,
                "quota_str": quota_str
            }'''

new_snippet = '''        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                user_data = data.get("user", {})
                quota_data = data.get("storageQuota", {})
                limit = int(quota_data.get("limit", 0))
                usage = int(quota_data.get("usage", 0))
                limit_gb = limit / (1024 ** 3)
                usage_gb = usage / (1024 ** 3)
                free_gb = max(0.0, limit_gb - usage_gb) if limit > 0 else 0.0
                quota_str = f"Занято {usage_gb:.1f} ГБ из {limit_gb:.1f} ГБ (свободно {free_gb:.1f} ГБ)" if limit > 0 else f"Занято {usage_gb:.1f} ГБ"
                return {
                    "success": True,
                    "ok": True,
                    "user": user_data.get("displayName", "Google User"),
                    "displayName": user_data.get("displayName", "Google User"),
                    "email": user_data.get("emailAddress", ""),
                    "emailAddress": user_data.get("emailAddress", ""),
                    "limit": limit,
                    "limit_gb": limit_gb,
                    "usage": usage,
                    "usage_gb": usage_gb,
                    "usageInDrive": int(quota_data.get("usageInDrive", 0)),
                    "free": max(0, limit - usage) if limit > 0 else 0,
                    "free_gb": free_gb,
                    "quota_str": quota_str
                }
        except urllib.error.HTTPError as he:
            return {"success": False, "ok": False, "error": f"HTTP Error {he.code}: {he.reason}"}
        except Exception as e:
            return {"success": False, "ok": False, "error": str(e)}'''

assert old_snippet in text, "old_snippet not found in google_drive.py"
text = text.replace(old_snippet, new_snippet)
p.write_text(text, encoding="utf-8")
print("test_connection now catches HTTPError cleanly!")
