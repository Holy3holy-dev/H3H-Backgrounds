with open('downloader/src/ui/app.cpp', 'r', encoding='utf-8') as f:
    c = f.read()

target = 'void App::openGamePicker'
first_pos = c.find(target)
second_pos = c.find(target, first_pos + len(target))
print('first_pos:', first_pos, 'second_pos:', second_pos)

if first_pos != -1 and second_pos != -1:
    # Delete from second_pos to the next '} // namespace ui\n} // namespace h3h'
    end_marker = '} // namespace ui\n} // namespace h3h'
    end_pos = c.find(end_marker, second_pos)
    c = c[:second_pos] + c[end_pos:]
    with open('downloader/src/ui/app.cpp', 'w', encoding='utf-8') as f:
        f.write(c)
    print('Cleaned up duplicate method definitions!')
