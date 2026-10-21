from pathlib import Path

app_path = Path("downloader/src/ui/app.cpp")
text = app_path.read_text(encoding="utf-8")

# Remove top faulty block
faulty_top = """#ifdef HAS_SDL2
static SDL_Texture* loadTextureFromFile(SDL_Renderer* renderer, const std::string& path) {
    if (!renderer || path.empty()) return nullptr;
    FILE* fp = fopen(path.c_str(), "rb");
    if (!fp) return nullptr;
    SDL_RWops* rw = SDL_RWFromFP(fp, SDL_TRUE);
    if (!rw) {
        fclose(fp);
        return nullptr;
    }
    SDL_Surface* surf = IMG_Load_RW(rw, 1);
    if (!surf) return nullptr;
    SDL_Texture* tex = SDL_CreateTextureFromSurface(renderer, surf);
    SDL_FreeSurface(surf);
    if (tex) {
        SDL_SetTextureBlendMode(tex, SDL_BLENDMODE_NONE);
    }
    return tex;
}
#endif
"""

if faulty_top in text:
    text = text.replace(faulty_top, "")
else:
    text = text.replace(faulty_top.replace("\n", "\r\n"), "")

# Add properly inside namespace h3h { namespace ui {
ns_anchor = """namespace h3h {
namespace ui {"""

helper_in_ns = """namespace h3h {
namespace ui {

#ifdef HAS_SDL2
namespace {
static SDL_Texture* loadTextureFromFile(SDL_Renderer* renderer, const std::string& path) {
    if (!renderer || path.empty()) return nullptr;
    FILE* fp = fopen(path.c_str(), "rb");
    if (!fp) return nullptr;
    SDL_RWops* rw = SDL_RWFromFP(fp, SDL_TRUE);
    if (!rw) {
        fclose(fp);
        return nullptr;
    }
    SDL_Surface* surf = IMG_Load_RW(rw, 1);
    if (!surf) return nullptr;
    SDL_Texture* tex = SDL_CreateTextureFromSurface(renderer, surf);
    SDL_FreeSurface(surf);
    if (tex) {
        SDL_SetTextureBlendMode(tex, SDL_BLENDMODE_NONE);
    }
    return tex;
}
} // anonymous namespace
#endif"""

if ns_anchor in text:
    text = text.replace(ns_anchor, helper_in_ns)
else:
    text = text.replace(ns_anchor.replace("\n", "\r\n"), helper_in_ns.replace("\n", "\r\n"))

app_path.write_text(text, encoding="utf-8")
print("[+] Fixed loadTextureFromFile placement in app.cpp")
