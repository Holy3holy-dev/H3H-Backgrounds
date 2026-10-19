#pragma once

#include <string>
#include <vector>
#include <cstdint>
#include <cstddef>

namespace h3h {

class SHA256 {
public:
    SHA256();
    void reset();
    void update(const uint8_t* data, size_t length);
    void update(const char* data, size_t length);
    void update(const std::string& str);
    
    // Finalizes and returns the 64-character lowercase hex string
    std::string finalHex();

    // Utility: compute SHA-256 of an entire file streaming in 64KB blocks
    static bool hashFile(const std::string& filePath, std::string& outHex);

    // Utility: compute SHA-256 of raw memory buffer
    static std::string hashBuffer(const void* data, size_t length);

private:
    void transform(const uint8_t* chunk);

    uint32_t m_state[8];
    uint64_t m_bitLength{0};
    uint8_t  m_buffer[64];
    size_t   m_bufferLength{0};
};

} // namespace h3h
