with open('downloader/src/ui/app.cpp', 'r', encoding='utf-8') as f:
    c = f.read()

target = '    // Target Game Picker Handler (Assign video theme to any installed game)\n    if (m_isGamePickerOpen'
first_pos = c.find(target)
second_pos = c.find(target, first_pos + len(target))
print('first_pos:', first_pos, 'second_pos:', second_pos)

if first_pos != -1 and second_pos != -1:
    # Delete between first_pos and second_pos
    c = c[:first_pos] + c[second_pos:]
    with open('downloader/src/ui/app.cpp', 'w', encoding='utf-8') as f:
        f.write(c)
    print('Cleaned up duplicate!')
