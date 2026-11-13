with open("downloader/src/platform/switch_platform.cpp", "r", encoding="utf-8") as f:
    code = f.read()

target = """            if (startPos >= responseBuffer.size() || (responseBuffer[startPos] != '{' && responseBuffer[startPos] != '[')) {
                lastFailureReason = "Ответ сервера не начинается с объекта JSON";
                continue;
            }

            // Successfully received and validated JSON buffer
            outJson = std::move(responseBuffer);
            return true;"""

replacement = """            if (startPos >= responseBuffer.size() || (responseBuffer[startPos] != '{' && responseBuffer[startPos] != '[')) {
                lastFailureReason = "Ответ сервера не начинается с объекта JSON";
                continue;
            }

            // Check end of response (ensure transfer was not truncated mid-stream)
            size_t endPos = responseBuffer.size();
            while (endPos > startPos &&
                   (responseBuffer[endPos - 1] == ' ' || responseBuffer[endPos - 1] == '\\t' ||
                    responseBuffer[endPos - 1] == '\\r' || responseBuffer[endPos - 1] == '\\n')) {
                endPos--;
            }

            if (endPos <= startPos || (responseBuffer[endPos - 1] != '}' && responseBuffer[endPos - 1] != ']')) {
                lastFailureReason = "Неполный ответ сервера (обрыв соединения во время передачи JSON)";
                continue;
            }

            // Shallow parse test to ensure complete and valid JSON before accepting this mirror
            try {
                auto testJson = nlohmann::json::parse(startPos == 0 ? responseBuffer : responseBuffer.substr(startPos));
                if (testJson.is_discarded()) {
                    lastFailureReason = "Поврежденная структура JSON (discarded)";
                    continue;
                }
            } catch (const std::exception& ex) {
                lastFailureReason = std::string("Синтаксическая ошибка в ответе: ") + ex.what();
                continue;
            }

            // Successfully received and validated complete JSON buffer
            outJson = std::move(responseBuffer);
            return true;"""

if target in code:
    code = code.replace(target, replacement)
    with open("downloader/src/platform/switch_platform.cpp", "w", encoding="utf-8") as f:
        f.write(code)
    print("[+] Successfully patched switch_platform.cpp")
else:
    print("[-] Target not found in switch_platform.cpp")
