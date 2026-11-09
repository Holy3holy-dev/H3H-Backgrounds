import os

with open('e:/videofon/scripts/update_app_cpp_v142.py', 'rb') as f:
    raw = f.read()

# Replace old_init_renderer with blank line
target = b'''old_init_renderer = """    m_renderer = SDL_CreateRenderer(
        m_window,
        -1,
        SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC
    );
    if (!m_renderer) {
        std::cerr << "[-] SDL_CreateRenderer failed: " << SDL_GetError() << std::endl;
        return false;
    }"""'''

replacement = b'''old_init_renderer = """    m_renderer = SDL_CreateRenderer(
        m_window,
        -1,
        SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC
    );

    if (!m_renderer) {
        std::cerr << "[-] SDL_CreateRenderer failed: " << SDL_GetError() << std::endl;
        return false;
    }"""'''

# Normalize CRLF/LF in target/replacement
target_crlf = target.replace(b'\n', b'\r\n')
replacement_crlf = replacement.replace(b'\n', b'\r\n')

if target_crlf in raw:
    raw = raw.replace(target_crlf, replacement_crlf, 1)
    print("Found CRLF target and replaced")
elif target in raw:
    raw = raw.replace(target, replacement, 1)
    print("Found LF target and replaced")
else:
    print("Target not found directly, checking normalized...")
    # fallback: normalize entire script to LF
    text = raw.decode('utf-8').replace('\r\n', '\n')
    text = text.replace(target.decode('utf-8'), replacement.decode('utf-8'))
    raw = text.encode('utf-8')
    print("Normalized replacement done")

with open('e:/videofon/scripts/update_app_cpp_v142.py', 'wb') as f:
    f.write(raw)

print("Saved update_app_cpp_v142.py")
