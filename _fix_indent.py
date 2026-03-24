import re

with open('musicisland.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

block_header_re = re.compile(r'^(\s*)(try:|except\b.*:|else:|finally:)\s*(#.*)?$')

fixes = []
for i in range(len(lines)):
    m = block_header_re.match(lines[i])
    if not m:
        continue
    header_indent = len(m.group(1))
    has_body = False
    for j in range(i+1, min(i+5, len(lines))):
        stripped = lines[j].strip()
        if stripped == '' or stripped.startswith('#'):
            continue
        line_indent = len(lines[j]) - len(lines[j].lstrip())
        if line_indent > header_indent:
            has_body = True
        break
    if not has_body:
        fixes.append(i)  # 0-indexed

print(f'Empty blocks at lines (1-indexed): {[x+1 for x in fixes]}')
print(f'Total: {len(fixes)}')

# Fix by inserting 'pass' after each empty block header
# Process in reverse order to not shift line indices
for idx in reversed(fixes):
    header_line = lines[idx]
    m = block_header_re.match(header_line)
    indent = m.group(1)
    pass_line = indent + '    pass\n'
    lines.insert(idx + 1, pass_line)

with open('musicisland.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Fixed all empty blocks.')
