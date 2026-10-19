#include "core/sha256.hpp"

#include <fstream>
#include <iomanip>
#include <sstream>
#include <cstring>

namespace h3h {

namespace {

inline uint32_t rotr(uint32_t x, uint32_t n) {
    return (x >> n) | (x << (32 - n));
}

inline uint32_t choose(uint32_t e, uint32_t f, uint32_t g) {
    return (e & f) ^ (~e & g);
}

inline uint32_t majority(uint32_t a, uint32_t b, uint32_t c) {
    return (a & b) ^ (a & c) ^ (b & c);
}

inline uint32_t sig0(uint32_t x) {
    return rotr(x, 2) ^ rotr(x, 13) ^ rotr(x, 22);
}

inline uint32_t sig1(uint32_t x) {
    return rotr(x, 6) ^ rotr(x, 11) ^ rotr(x, 25);
}

inline uint32_t theta0(uint32_t x) {
    return rotr(x, 7) ^ rotr(x, 18) ^ (x >> 3);
}

inline uint32_t theta1(uint32_t x) {
    return rotr(x, 17) ^ rotr(x, 19) ^ (x >> 10);
}

const uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

} // namespace

SHA256::SHA256() {
    reset();
}

void SHA256::reset() {
    m_state[0] = 0x6a09e667;
    m_state[1] = 0xbb67ae85;
    m_state[2] = 0x3c6ef372;
    m_state[3] = 0xa54ff53a;
    m_state[4] = 0x510e527f;
    m_state[5] = 0x9b05688c;
    m_state[6] = 0x1f83d9ab;
    m_state[7] = 0x5be0cd19;
    m_bitLength = 0;
    m_bufferLength = 0;
}

void SHA256::transform(const uint8_t* chunk) {
    uint32_t w[64];
    for (size_t i = 0; i < 16; ++i) {
        w[i] = (static_cast<uint32_t>(chunk[i * 4]) << 24) |
               (static_cast<uint32_t>(chunk[i * 4 + 1]) << 16) |
               (static_cast<uint32_t>(chunk[i * 4 + 2]) << 8) |
               (static_cast<uint32_t>(chunk[i * 4 + 3]));
    }
    for (size_t i = 16; i < 64; ++i) {
        w[i] = theta1(w[i - 2]) + w[i - 7] + theta0(w[i - 15]) + w[i - 16];
    }

    uint32_t a = m_state[0];
    uint32_t b = m_state[1];
    uint32_t c = m_state[2];
    uint32_t d = m_state[3];
    uint32_t e = m_state[4];
    uint32_t f = m_state[5];
    uint32_t g = m_state[6];
    uint32_t h = m_state[7];

    for (size_t i = 0; i < 64; ++i) {
        uint32_t t1 = h + sig1(e) + choose(e, f, g) + K[i] + w[i];
        uint32_t t2 = sig0(a) + majority(a, b, c);
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }

    m_state[0] += a;
    m_state[1] += b;
    m_state[2] += c;
    m_state[3] += d;
    m_state[4] += e;
    m_state[5] += f;
    m_state[6] += g;
    m_state[7] += h;
}

void SHA256::update(const uint8_t* data, size_t length) {
    m_bitLength += length * 8;
    for (size_t i = 0; i < length; ++i) {
        m_buffer[m_bufferLength++] = data[i];
        if (m_bufferLength == 64) {
            transform(m_buffer);
            m_bufferLength = 0;
        }
    }
}

void SHA256::update(const char* data, size_t length) {
    update(reinterpret_cast<const uint8_t*>(data), length);
}

void SHA256::update(const std::string& str) {
    update(str.data(), str.size());
}

std::string SHA256::finalHex() {
    uint64_t totalBits = m_bitLength;

    // Append 0x80 padding byte
    m_buffer[m_bufferLength++] = 0x80;

    // If buffer length exceeds 56, pad with zeros, transform, and start next block
    if (m_bufferLength > 56) {
        while (m_bufferLength < 64) {
            m_buffer[m_bufferLength++] = 0x00;
        }
        transform(m_buffer);
        m_bufferLength = 0;
    }

    // Pad with zeros up to byte 56
    while (m_bufferLength < 56) {
        m_buffer[m_bufferLength++] = 0x00;
    }

    // Append 64-bit big-endian original message length in bits
    for (int i = 7; i >= 0; --i) {
        m_buffer[56 + (7 - i)] = static_cast<uint8_t>((totalBits >> (i * 8)) & 0xFF);
    }
    transform(m_buffer);

    std::ostringstream ss;
    ss << std::hex << std::setfill('0');
    for (size_t i = 0; i < 8; ++i) {
        ss << std::setw(8) << m_state[i];
    }
    return ss.str();
}

bool SHA256::hashFile(const std::string& filePath, std::string& outHex) {
    std::ifstream file(filePath, std::ios::binary);
    if (!file.is_open()) {
        return false;
    }

    SHA256 sha;
    char buffer[65536];
    while (file.read(buffer, sizeof(buffer)) || file.gcount() > 0) {
        sha.update(buffer, static_cast<size_t>(file.gcount()));
    }

    outHex = sha.finalHex();
    return true;
}

std::string SHA256::hashBuffer(const void* data, size_t length) {
    SHA256 sha;
    sha.update(reinterpret_cast<const uint8_t*>(data), length);
    return sha.finalHex();
}

} // namespace h3h
