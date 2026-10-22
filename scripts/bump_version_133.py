from pathlib import Path
import json

# 1. config.hpp
cfg = Path("downloader/include/core/config.hpp")
txt = cfg.read_text(encoding="utf-8")
txt = txt.replace('"1.3.2"', '"1.3.3"')
cfg.write_text(txt, encoding="utf-8")
print("[+] config.hpp bumped to 1.3.3")

# 2. Makefile
mk = Path("downloader/Makefile")
txt = mk.read_text(encoding="utf-8")
txt = txt.replace("APP_VERSION := 1.3.2", "APP_VERSION := 1.3.3")
mk.write_text(txt, encoding="utf-8")
print("[+] Makefile bumped to 1.3.3")

# 3. version.json
vj = Path("version.json")
v_data = json.loads(vj.read_text(encoding="utf-8"))
v_data["latestVersion"] = "1.3.3"
v_data["downloadUrl"] = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.3.3/H3H-Backgrounds.nro"
v_data["afterDarkDownloadUrl"] = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.3.3/H3H-AfterDark.nro"
v_data["releaseNotes"] = "v1.3.3: 🎯 Точное распознавание установленного варианта (GTA 5 и др.), мгновенное обновление статуса без перезапуска и плавный скролл пальцем в каталоге"
vj.write_text(json.dumps(v_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("[+] version.json bumped to 1.3.3")
