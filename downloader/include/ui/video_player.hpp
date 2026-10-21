#pragma once

#include <string>
#include <cstdint>
#include <cstdio>

#ifdef HAS_SDL2
#include <SDL2/SDL.h>

extern "C" {
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavformat/avio.h>
#include <libswscale/swscale.h>
#include <libavutil/imgutils.h>
#include <libavutil/time.h>
}

namespace h3h {
namespace ui {

class VideoPlayer {
public:
    VideoPlayer();
    ~VideoPlayer();

    bool open(const std::string& filepath, SDL_Renderer* renderer);
    void close();
    void update();
    void render(SDL_Renderer* renderer, const SDL_Rect* dstRect = nullptr);

    bool isPlaying() const { return m_isOpen && m_hasDecodedFirstFrame; }
    int getWidth() const { return m_width; }
    int getHeight() const { return m_height; }
    double getFps() const { return m_fps; }
    const std::string& getFilePath() const { return m_filepath; }

private:
    std::string m_filepath;
    bool m_isOpen{false};
    bool m_hasDecodedFirstFrame{false};
    int m_width{0};
    int m_height{0};
    int m_targetWidth{1280};
    int m_targetHeight{720};
    double m_fps{30.0};
    int64_t m_frameIntervalMs{33};
    uint32_t m_lastFrameTime{0};

    FILE* m_fileHandle{nullptr};
    uint8_t* m_avioBuffer{nullptr};
    AVIOContext* m_avioCtx{nullptr};

    AVFormatContext* m_formatCtx{nullptr};
    AVCodecContext* m_codecCtx{nullptr};
    SwsContext* m_swsCtx{nullptr};
    AVFrame* m_frame{nullptr};
    AVFrame* m_frameRGB{nullptr};
    AVPacket* m_packet{nullptr};
    uint8_t* m_rgbBuffer{nullptr};
    int m_videoStream{-1};

    SDL_Texture* m_texture{nullptr};
};

} // namespace ui
} // namespace h3h
#endif
