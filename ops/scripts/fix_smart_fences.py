#!/usr/bin/env python3
"""
智能修復 Markdown code fence 配對問題
處理 blockquote 內的 fence
"""
import re

def fix_markdown_fences(filepath):
    """修復所有 fence 配對問題"""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    fixed_lines = []
    fence_stack = []  # 追蹤未閉合的 fence
    
    for i, line in enumerate(lines, 1):
        # 檢測各種形式的 fence
        fence_match = re.match(r'^(\s*>?\s*)(```\w*)\s*$', line)
        
        if fence_match:
            indent = fence_match.group(1)
            fence = fence_match.group(2)
            
            # 如果是在 blockquote 內
            if '>' in indent:
                # 確保 opening 和 closing fence 都在同一層級的 blockquote 內
                if fence_stack and fence_stack[-1]['in_quote']:
                    # Closing fence
                    fence_stack.pop()
                    fixed_lines.append(line)
                else:
                    # Opening fence in quote
                    fence_stack.append({'line': i, 'in_quote': True, 'indent': indent})
                    fixed_lines.append(line)
            else:
                # 普通 fence
                if fence_stack and not fence_stack[-1]['in_quote']:
                    # Closing fence
                    fence_stack.pop()
                    fixed_lines.append(line)
                elif not fence_stack:
                    # Opening fence
                    fence_stack.append({'line': i, 'in_quote': False, 'indent': indent})
                    fixed_lines.append(line)
                else:
                    # Mismatch: quote opened, normal close
                    # 關閉 quote fence
                    quote_fence = fence_stack.pop()
                    # 插入一個在 quote 內的 closing fence
                    fixed_lines.append(f'{quote_fence["indent"]}```\n')
                    print(f"⚠️  Line {i}: Added missing closing fence for blockquote fence at line {quote_fence['line']}")
                    # 然後處理當前的普通 fence
                    fence_stack.append({'line': i, 'in_quote': False, 'indent': indent})
                    fixed_lines.append(line)
        else:
            fixed_lines.append(line)
    
    # 補齊未閉合的 fence
    while fence_stack:
        unclosed = fence_stack.pop()
        if unclosed['in_quote']:
            fixed_lines.append(f'{unclosed["indent"]}```\n')
        else:
            fixed_lines.append('```\n')
        print(f"⚠️  Added closing fence for unclosed fence at line {unclosed['line']}")
    
    # 寫入修復後的檔案
    output_path = filepath.replace('.md', '_fixed.md')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)
    
    print(f"✅ Fixed file saved to: {output_path}")
    return output_path

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python fix_smart_fences.py <markdown_file>")
        sys.exit(1)
    
    fix_markdown_fences(sys.argv[1])
