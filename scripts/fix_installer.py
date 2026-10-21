with open('downloader/src/core/installer.cpp', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('find(""error"")', 'find("error")')
text = text.replace('find(""message"")', 'find("message")')
text = text.replace('issue.fileSizeBytes', 'issue.sizeBytes')

with open('downloader/src/core/installer.cpp', 'w', encoding='utf-8') as f:
    f.write(text)

print('Successfully fixed installer.cpp')
