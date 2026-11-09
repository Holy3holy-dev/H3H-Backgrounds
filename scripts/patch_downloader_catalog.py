from pathlib import Path

p = Path("downloader/src/core/catalog_manager.cpp")
code = p.read_text(encoding="utf-8")

old_sec_check = '''                    // Security check on download URL
                    if (v.url.rfind("https://", 0) != 0) {
                        outError = "Insecure or invalid variant URL: " + v.url;
                        return false;
                    }'''

new_sec_check = '''                    v.hasIcon = jVar.value("hasIcon", false);
                    v.iconUrl = jVar.value("iconUrl", "");
                    v.iconSizeBytes = jVar.value("iconSizeBytes", static_cast<uint64_t>(0));
                    v.iconCodec = jVar.value("iconCodec", "hevc");
                    v.iconWidth = jVar.value("iconWidth", 256);
                    v.iconHeight = jVar.value("iconHeight", 256);
                    if (!v.iconUrl.empty()) {
                        v.hasIcon = true;
                    }

                    // Security check on download URLs
                    if (!v.url.empty() && v.url.rfind("https://", 0) != 0) {
                        outError = "Insecure or invalid variant URL: " + v.url;
                        return false;
                    }
                    if (!v.iconUrl.empty() && v.iconUrl.rfind("https://", 0) != 0) {
                        outError = "Insecure or invalid icon URL: " + v.iconUrl;
                        return false;
                    }'''

assert old_sec_check in code, "old_sec_check not found"
code = code.replace(old_sec_check, new_sec_check, 1)

p.write_text(code, encoding="utf-8")
print("[+] Updated downloader/src/core/catalog_manager.cpp")
