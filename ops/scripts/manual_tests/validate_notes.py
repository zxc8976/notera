#!/usr/bin/env python3
"""筆記品質驗證腳本 - 自動檢測常見格式問題"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

class NoteValidator:
    """筆記驗證器"""
    
    def __init__(self, note_path: Path):
        self.note_path = note_path
        self.content = self._read_note()
        self.issues = []
    
    def _read_note(self) -> str:
        """讀取筆記內容"""
        try:
            with open(self.note_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"❌ 無法讀取檔案 {self.note_path}: {e}")
            sys.exit(1)
    
    def check_html_tags(self) -> None:
        """檢查 HTML 標籤殘留（排除程式碼區塊）"""
        # 移除程式碼區塊
        code_removed = re.sub(r'```[\s\S]*?```', '', self.content)
        
        # 尋找 HTML 標籤
        html_patterns = [
            r'</?span[^>]*>',
            r'</?mark[^>]*>',
            r'</?div[^>]*>',
            r'</?p[^>]*>',
            r'style="[^"]*"',
            r'class="[^"]*"'
        ]
        
        total_tags = 0
        for pattern in html_patterns:
            matches = re.findall(pattern, code_removed, re.IGNORECASE)
            total_tags += len(matches)
        
        if total_tags > 0:
            self.issues.append(f"發現 {total_tags} 個 HTML 標籤或屬性殘留")
    
    def check_japanese_wrapping(self) -> None:
        """檢查日文原文是否被錯誤包裹"""
        # 尋找日文原文段落
        jp_section = re.search(
            r'##\s*[🇯🇵]*\s*日文原文(.*?)(?=##|$)', 
            self.content, 
            re.DOTALL
        )
        
        if jp_section:
            jp_content = jp_section.group(1)
            
            # 檢查是否有程式碼區塊標記
            if '```' in jp_content:
                # 確認是否為真實程式碼
                code_blocks = re.findall(r'```([\w]*)\n([\s\S]*?)\n```', jp_content)
                for lang, code in code_blocks:
                    # 檢查是否為誤判
                    cjk_ratio = len(re.findall(r'[\u3040-\u30ff\u3400-\u9fff]', code)) / max(len(code), 1)
                    if cjk_ratio > 0.3:  # 30% 以上是中日文
                        self.issues.append("日文原文被錯誤包裹在程式碼區塊中")
                        break
    
    def check_code_analysis(self) -> None:
        """檢查程式碼區塊是否有分析"""
        # 尋找所有程式碼區塊
        code_blocks = re.findall(r'```[\w]*\n[\s\S]*?```', self.content)
        
        # 尋找分析區塊
        analysis_count = len(re.findall(r'執行結果分析|Execution.*Analysis', self.content, re.IGNORECASE))
        
        if len(code_blocks) > 0 and analysis_count == 0:
            self.issues.append(f"有 {len(code_blocks)} 個程式碼區塊但無執行結果分析")
    
    def check_vocab_table(self) -> None:
        """檢查術語對照表"""
        # 檢查是否包含技術術語
        tech_terms = ['String', 'StringBuilder', '文字列', 'メモリ', '比較']
        has_tech_content = any(term in self.content for term in tech_terms)
        
        # 檢查是否有術語表
        has_vocab_table = bool(re.search(r'##\s*[📚🔤].*?(詞彙|術語|Vocabulary)', self.content, re.IGNORECASE))
        
        if has_tech_content and not has_vocab_table:
            self.issues.append("包含技術術語但缺少關鍵術語對照表")
    
    def check_heading_format(self) -> None:
        """檢查標題格式"""
        # 尋找格式不正確的標題（# 後無空格）
        bad_headings = re.findall(r'^(#+)([^\s#])', self.content, re.MULTILINE)
        
        if bad_headings:
            self.issues.append(f"發現 {len(bad_headings)} 個格式不正確的標題（# 後缺少空格）")
    
    def check_list_format(self) -> None:
        """檢查列表格式"""
        # 尋找格式不正確的列表項（- 後無空格）
        bad_lists = re.findall(r'^-([^\s-])', self.content, re.MULTILINE)
        
        if bad_lists:
            self.issues.append(f"發現 {len(bad_lists)} 個格式不正確的列表項（- 後缺少空格）")
    
    def check_empty_sections(self) -> None:
        """檢查空段落"""
        # 尋找標題後直接接另一個標題（中間無內容）
        empty_sections = re.findall(r'##[^\n]+\n\s*##', self.content)
        
        if empty_sections:
            self.issues.append(f"發現 {len(empty_sections)} 個空段落（標題後無內容）")
    
    def run_all_checks(self) -> Tuple[bool, List[str]]:
        """執行所有檢查"""
        self.check_html_tags()
        self.check_japanese_wrapping()
        self.check_code_analysis()
        self.check_vocab_table()
        self.check_heading_format()
        self.check_list_format()
        self.check_empty_sections()
        
        return len(self.issues) == 0, self.issues

def main():
    """主程式"""
    notes_dir = Path("output/notes")
    
    if not notes_dir.exists():
        print("❌ 筆記目錄不存在：output/notes")
        print("💡 請確認路徑或先生成一些筆記")
        sys.exit(1)
    
    # 尋找所有 markdown 檔案
    note_files = list(notes_dir.glob("*.md"))
    
    if not note_files:
        print("⚠️  筆記目錄為空")
        print("💡 請先生成一些筆記後再執行驗證")
        sys.exit(0)
    
    print(f"🔍 開始驗證 {len(note_files)} 個筆記檔案...\n")
    
    results = []
    for note_file in note_files:
        validator = NoteValidator(note_file)
        is_valid, issues = validator.run_all_checks()
        results.append(is_valid)
        
        if is_valid:
            print(f"✅ {note_file.name} - 格式正確")
        else:
            print(f"❌ {note_file.name} - 發現 {len(issues)} 個問題：")
            for issue in issues:
                print(f"   • {issue}")
        print()
    
    # 輸出統計
    success_count = sum(results)
    total_count = len(results)
    success_rate = success_count / total_count * 100 if total_count > 0 else 0
    
    print("=" * 60)
    print(f"📊 測試結果：{success_count}/{total_count} 通過 ({success_rate:.1f}%)")
    print("=" * 60)
    
    # 評級
    if success_rate >= 90:
        print("🏆 評級：A 級（優秀）")
    elif success_rate >= 70:
        print("⭐ 評級：B 級（良好）")
    elif success_rate >= 50:
        print("⚠️  評級：C 級（尚可）")
    else:
        print("❌ 評級：D 級（需改進）")
    
    # 建議
    if success_rate < 100:
        print("\n💡 改進建議：")
        print("   1. 檢查 modules/note_generator.py 中的清理邏輯")
        print("   2. 確認 _enhance_note_content() 是否正確執行")
        print("   3. 重啟後端服務：docker-compose restart notegen")
        print("   4. 參考文檔：docs/NOTE_OUTPUT_OPTIMIZATION.md")
    
    sys.exit(0 if success_rate == 100 else 1)

if __name__ == "__main__":
    main()
