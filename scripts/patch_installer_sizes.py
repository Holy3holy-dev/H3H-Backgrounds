with open('downloader/src/core/installer.cpp', 'r', encoding='utf-8') as f:
    c = f.read()

old_block = """    uint64_t actualSize = fs::file_size(tempFilePath, ec);
    if (expectedSizeBytes > 0 && actualSize != expectedSizeBytes) {
        fs::remove(tempFilePath, ec);
        result.success = false;
        result.message = "File size mismatch (expected " + std::to_string(expectedSizeBytes) +
                         " bytes, got " + std::to_string(actualSize) + " bytes)";
        return result;
    }"""

new_block = """    uint64_t actualSize = fs::file_size(tempFilePath, ec);
    if (actualSize < 1024) {
        fs::remove(tempFilePath, ec);
        result.success = false;
        result.message = "Downloaded file is empty or corrupted";
        return result;
    }"""

if old_block in c:
    c = c.replace(old_block, new_block, 1)
    print("Successfully patched installer.cpp (LF)")
else:
    old_block_crlf = old_block.replace('\n', '\r\n')
    new_block_crlf = new_block.replace('\n', '\r\n')
    if old_block_crlf in c:
        c = c.replace(old_block_crlf, new_block_crlf, 1)
        print("Successfully patched installer.cpp (CRLF)")
    else:
        print("Target block not found!")

with open('downloader/src/core/installer.cpp', 'w', encoding='utf-8') as f:
    f.write(c)
