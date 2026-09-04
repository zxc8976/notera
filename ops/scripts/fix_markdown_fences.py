#!/usr/bin/env python3
"""
Standalone markdown fence repair script.
Fixes malformed code fences in generated notes.
"""
import re
import sys

def repair_code_fences_simple(text):
    """Simple, reliable fence repair."""
    lines = text.splitlines()
    fence_re = re.compile(r"^(\s*)```(\S*)?\s*$")
    result = []
    skip_next = False
    
    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue
        
        match = fence_re.match(line)
        if match and i + 1 < len(lines):
            lang = (match.group(2) or "").strip()
            next_match = fence_re.match(lines[i + 1])
            
            if next_match:
                next_lang = (next_match.group(2) or "").strip()
                # Remove malformed ``` after ```lang or consecutive ```
                if (lang and not next_lang) or (not lang and not next_lang):
                    result.append(line)
                    skip_next = True
                    continue
        
        result.append(line)
    
    return "\n".join(result)

def clean_file(filepath):
    """Clean a single markdown file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    before = len(re.findall(r'\n```\n', content))
    cleaned = repair_code_fences_simple(content)
    after = len(re.findall(r'\n```\n', cleaned))
    
    if before > after:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(cleaned)
        print(f"✅ {filepath}: {before} → {after} (removed {before - after})")
        return True
    else:
        print(f"⏭️  {filepath}: No malformed fences found")
        return False

if __name__ == "__main__":
    import glob
    
    # Fix all markdown files in var/output
    files = glob.glob('/app/var/output/*.md')
    fixed = 0
    
    for filepath in files:
        if clean_file(filepath):
            fixed += 1
    
    print(f"\n📊 Summary: Fixed {fixed}/{len(files)} files")
