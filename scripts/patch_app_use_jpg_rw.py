from pathlib import Path

p = Path("downloader/src/ui/app.cpp")
text = p.read_text(encoding="utf-8").replace("\r\n", "\n")

# 1. Remove IMG_Init call
text = text.replace("    IMG_Init(IMG_INIT_JPG | IMG_INIT_PNG);\n", "")

# 2. In update(), use IMG_LoadJPG_RW
old_update_load = """        SDL_Surface* surf = IMG_Load(path.c_str());
        if (surf) {
            if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
            m_previewTexture = SDL_CreateTextureFromSurface(m_renderer, surf);
            SDL_FreeSurface(surf);
        }"""

new_update_load = """        SDL_RWops* rw = SDL_RWFromFile(path.c_str(), "rb");
        if (rw) {
            SDL_Surface* surf = IMG_LoadJPG_RW(rw);
            if (surf) {
                if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
                m_previewTexture = SDL_CreateTextureFromSurface(m_renderer, surf);
                SDL_FreeSurface(surf);
            }
        }"""

text = text.replace(old_update_load, new_update_load)

# 3. In loadPreviewTexture(), use IMG_LoadJPG_RW
old_preview_load = """    if (std::filesystem::exists(thumbFile, ec)) {
        SDL_Surface* surf = IMG_Load(thumbFile.c_str());
        if (surf) {
            m_previewTexture = SDL_CreateTextureFromSurface(m_renderer, surf);
            SDL_FreeSurface(surf);
            return;
        }
    }"""

new_preview_load = """    if (std::filesystem::exists(thumbFile, ec)) {
        SDL_RWops* rw = SDL_RWFromFile(thumbFile.c_str(), "rb");
        if (rw) {
            SDL_Surface* surf = IMG_LoadJPG_RW(rw);
            if (surf) {
                m_previewTexture = SDL_CreateTextureFromSurface(m_renderer, surf);
                SDL_FreeSurface(surf);
                return;
            }
        }
    }"""

text = text.replace(old_preview_load, new_preview_load)

p.write_text(text, encoding="utf-8")
print("[+] Updated app.cpp to use IMG_LoadJPG_RW directly")
