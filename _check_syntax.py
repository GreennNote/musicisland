import ast

try:
    with open('musicisland.py', 'r', encoding='utf-8') as f:
        content = f.read()
    ast.parse(content)
    result = 'No syntax errors!'
except SyntaxError as e:
    result = f'Syntax error at line {e.lineno}: {e.msg}'

with open('_check.txt', 'w') as f:
    f.write(result)
