#!/usr/bin/env python3
"""
修復 Markdown 檔案中不配對的 code fence
"""
import sys
import re

def fix_fence_pairing(filepath):
    """修復 code fence 配對問題"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    in_fence = False
    fence_count = 0
    fixed_lines = []
    
    for i, line in enumerate(lines, 1):
        # 檢測 code fence
        if re.match(r'^\s*```', line):
            fence_count += 1
            in_fence = not in_fence
            fixed_lines.append(line)
            print(f"Line {i}: Found fence #{fence_count} - {'OPEN' if in_fence else 'CLOSE'}: {line[:50]}")
        else:
            fixed_lines.append(line)
    
    # 如果 fence 數量是奇數，在檔案最後補一個
    if fence_count % 2 == 1:
        print(f"\n⚠️  Found {fence_count} fences (odd number) - adding closing fence at end")
        fixed_lines.append("\n```\n")
        fence_count += 1
    
    print(f"\n✅ Total fences: {fence_count} ({'BALANCED' if fence_count % 2 == 0 else 'UNBALANCED'})")
    
    # 寫回檔案
    output_path = filepath.replace('.md', '_fixed.md')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(fixed_lines))
    
    print(f"💾 Fixed file saved to: {output_path}")
    return output_path

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python fix_fence_pairing.py <markdown_file>")
        sys.exit(1)
    
    filepath = sys.argv[1]
    fix_fence_pairing(filepath)
