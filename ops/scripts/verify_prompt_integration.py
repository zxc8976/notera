#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
快速驗證優化版 Prompt 整合
執行此腳本以驗證所有組件是否正確整合
"""

import sys\nimport os\nfrom pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]\nBACKEND_SRC = REPO_ROOT / "source" / "backend"\nsys.path.insert(0, str(BACKEND_SRC))\n
def test_optimized_prompt_import():
    """測試優化版 Prompt 模組是否可以導入"""
    print("=" * 60)
    print("測試 1: 檢查優化版 Prompt 模組")
    print("=" * 60)
    
    try:
        from modules.llm_prompts_optimized import get_optimized_image_note_prompt
        print("✅ 成功導入 llm_prompts_optimized 模組")
        
        # 測試函數調用
        test_ocr = "これはテストです。"
        prompt = get_optimized_image_note_prompt(test_ocr, "zh-TW")
        
        # 檢查 Prompt 結構
        required_sections = [
            "📋 快速摘要",
            "📖 句子詳解",
            "📚 詞彙強化",
            "🎓 學習補充"
        ]
        
        missing_sections = []
        for section in required_sections:
            if section not in prompt:
                missing_sections.append(section)
        
        if missing_sections:
            print(f"⚠️ 警告: 缺少以下區塊: {', '.join(missing_sections)}")
            return False
        else:
            print("✅ Prompt 結構完整 (包含所有必要區塊)")
            print(f"✅ Prompt 長度: {len(prompt)} 字元")
            return True
            
    except ImportError as e:
        print(f"❌ 無法導入模組: {e}")
        return False
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False

def test_config_option():
    """測試配置選項是否存在"""
    print("\n" + "=" * 60)
    print("測試 2: 檢查配置選項")
    print("=" * 60)
    
    try:
        import yaml
        config_path = BACKEND_SRC / "app" / "config.yaml"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if 'output' in config and 'use_optimized_format' in config['output']:
            value = config['output']['use_optimized_format']
            print(f"✅ 配置選項存在: output.use_optimized_format = {value}")
            
            if value:
                print("ℹ️ 優化版 Prompt 已啟用")
            else:
                print("ℹ️ 優化版 Prompt 未啟用 (使用舊版)")
            
            return True
        else:
            print("❌ 配置選項不存在: output.use_optimized_format")
            return False
            
    except FileNotFoundError:
        print(f"❌ 找不到配置文件: {config_path}")
        return False
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False

def test_image_analyzer_integration():
    """測試 Image Analyzer 整合"""
    print("\n" + "=" * 60)
    print("測試 3: 檢查 Image Analyzer 整合")
    print("=" * 60)
    
    try:
        # 檢查文件是否存在
        analyzer_path = BACKEND_SRC / "modules" / "image_analyzer.py"

        with open(analyzer_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 檢查關鍵代碼
        required_imports = [
            'from .llm_prompts_v2 import get_strict_image_note_prompt',
            'from .llm_prompts_optimized import get_optimized_image_note_prompt'
        ]
        
        required_logic = [
            "use_optimized = self.config.get('output', {}).get('use_optimized_format', False)",
            'if use_optimized and language == "zh-TW":'
        ]
        
        missing = []
        
        for code in required_imports:
            if code not in content:
                missing.append(f"導入: {code}")
        
        for code in required_logic:
            if code not in content:
                missing.append(f"邏輯: {code}")
        
        if missing:
            print("❌ 缺少以下代碼:")
            for item in missing:
                print(f"   - {item}")
            return False
        else:
            print("✅ Image Analyzer 已正確整合")
            print("✅ 包含新舊 Prompt 切換邏輯")
            return True
            
    except FileNotFoundError:
        print(f"❌ 找不到文件: {analyzer_path}")
        return False
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False

def test_api_routes_update():
    """測試 API Routes 更新"""
    print("\n" + "=" * 60)
    print("測試 4: 檢查 API Routes 更新")
    print("=" * 60)
    
    try:
        routes_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'modules', 
            'api_routes.py'
        )
        
        with open(routes_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 檢查 MATH_CHAT_GUIDELINES 是否包含新結構
        required_sections = [
            "第一段：快速理解",
            "第二段：逐步拆解",
            "第三段：學習深化"
        ]
        
        missing = []
        for section in required_sections:
            if section not in content:
                missing.append(section)
        
        if missing:
            print(f"⚠️ 數學教學 Prompt 可能未完全更新")
            print(f"   缺少: {', '.join(missing)}")
            return False
        else:
            print("✅ API Routes 數學教學 Prompt 已更新")
            print("✅ 採用三段式結構")
            return True
            
    except FileNotFoundError:
        print(f"❌ 找不到文件: {routes_path}")
        return False
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False

def test_documentation():
    """測試文檔完整性"""
    print("\n" + "=" * 60)
    print("測試 5: 檢查文檔完整性")
    print("=" * 60)
    
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs')
    
    required_docs = [
        'NOTE_OUTPUT_OPTIMIZATION_PLAN.md',
        'NOTE_OUTPUT_OPTIMIZED_PROMPT.md',
        'NOTE_OUTPUT_OPTIMIZATION_EXECUTION_REPORT.md',
        'NOTE_OUTPUT_INTEGRATION_COMPLETE.md'
    ]
    
    missing_docs = []
    for doc in required_docs:
        doc_path = os.path.join(docs_dir, doc)
        if not os.path.exists(doc_path):
            missing_docs.append(doc)
    
    if missing_docs:
        print("❌ 缺少以下文檔:")
        for doc in missing_docs:
            print(f"   - {doc}")
        return False
    else:
        print("✅ 所有必要文檔都已創建")
        for doc in required_docs:
            doc_path = os.path.join(docs_dir, doc)
            size = os.path.getsize(doc_path) / 1024  # KB
            print(f"   ✓ {doc} ({size:.1f} KB)")
        return True

def run_all_tests():
    """執行所有測試"""
    print("\n" + "🚀" * 30)
    print("優化版 Prompt 整合驗證")
    print("🚀" * 30 + "\n")
    
    results = {
        "優化 Prompt 模組": test_optimized_prompt_import(),
        "配置選項": test_config_option(),
        "Image Analyzer 整合": test_image_analyzer_integration(),
        "API Routes 更新": test_api_routes_update(),
        "文檔完整性": test_documentation()
    }
    
    print("\n" + "=" * 60)
    print("📊 測試結果總結")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"{status} - {test_name}")
    
    print("\n" + "-" * 60)
    print(f"總計: {passed}/{total} 測試通過")
    
    if passed == total:
        print("\n🎉 恭喜!所有整合測試通過!")
        print("\n下一步:")
        print("1. 修改 config.yaml,將 use_optimized_format 改為 true")
        print("2. 重啟容器: docker-compose restart backend")
        print("3. 上傳測試圖片驗證效果")
        print("4. 記錄測試結果")
        return 0
    else:
        print("\n⚠️ 有測試失敗,請檢查上述錯誤訊息")
        print("\n建議:")
        print("1. 檢查是否所有文件都正確修改")
        print("2. 確認沒有語法錯誤")
        print("3. 查看詳細錯誤訊息")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)



