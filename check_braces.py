with open('static/js/apontamento-persistence.js', 'r', encoding='utf-8') as f:
    content = f.read()
    opens = content.count('{')
    closes = content.count('}')
    print(f'Opens: {opens}, Closes: {closes}, Diff: {opens - closes}')
    
    # Find unmatched braces
    stack = []
    for i, char in enumerate(content):
        if char == '{':
            stack.append(i)
        elif char == '}':
            if stack:
                stack.pop()
            else:
                line = content[:i].count('\n') + 1
                print(f'Extra closing brace at line {line}')
    
    if stack:
        for pos in stack[-5:]:  # Show last 5 unmatched
            line = content[:pos].count('\n') + 1
            print(f'Unclosed opening brace at line {line}')
