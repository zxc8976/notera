/**
 * Grounding 驗證工具
 * 確保生成的內容與 OCR 文本相關
 */

// 關鍵詞白名單
const KEYWORD_WHITELIST = [
  'String', 'StringBuilder', 'equals', '==', 'System.out.print',
  '記憶體', '參照', '內容', 'Object', 'false', 'true',
  'コンパイル', '実行', 'プログラム', 'メソッド', 'クラス'
]

/**
 * 計算文本相似度（簡單的 TF-IDF 方法）
 */
function calculateSimilarity(text1, text2) {
  if (!text1 || !text2) return 0
  
  const words1 = text1.toLowerCase().split(/\s+/)
  const words2 = text2.toLowerCase().split(/\s+/)
  
  const set1 = new Set(words1)
  const set2 = new Set(words2)
  
  const intersection = new Set([...set1].filter(x => set2.has(x)))
  const union = new Set([...set1, ...set2])
  
  return intersection.size / union.size
}

/**
 * 檢查關鍵詞命中率
 */
function checkKeywordHit(text, minHits = 3) {
  if (!text) return false
  
  const textLower = text.toLowerCase()
  const hits = KEYWORD_WHITELIST.filter(keyword => 
    textLower.includes(keyword.toLowerCase())
  )
  
  return hits.length >= minHits
}

/**
 * 驗證單個筆記項目
 */
export function validateNoteItem(note, ocrText) {
  if (!note || !ocrText) {
    return { valid: false, reason: '缺少必要資料' }
  }
  
  // 檢查關鍵詞命中
  const hasKeywords = checkKeywordHit(note.original || note.explanation || '')
  if (!hasKeywords) {
    return { valid: false, reason: '關鍵詞命中不足' }
  }
  
  // 檢查相似度
  const similarity = calculateSimilarity(
    (note.original || '') + ' ' + (note.explanation || ''),
    ocrText
  )
  
  if (similarity < 0.3) {
    return { valid: false, reason: '與 OCR 內容相似度過低' }
  }
  
  return { valid: true, similarity }
}

/**
 * 驗證程式碼區塊
 */
export function validateCodeBlock(codeBlock, ocrText) {
  if (!codeBlock || !codeBlock.code || !ocrText) {
    return { valid: false, reason: '缺少程式碼或 OCR 資料' }
  }
  
  // 檢查程式碼中的關鍵詞
  const hasKeywords = checkKeywordHit(codeBlock.code, 2)
  if (!hasKeywords) {
    return { valid: false, reason: '程式碼關鍵詞命中不足' }
  }
  
  // 檢查程式碼與 OCR 的相似度
  const similarity = calculateSimilarity(codeBlock.code, ocrText)
  if (similarity < 0.2) {
    return { valid: false, reason: '程式碼與 OCR 內容相似度過低' }
  }
  
  return { valid: true, similarity }
}

/**
 * 驗證 Q&A 項目
 */
export function validateQAItem(qaItem, ocrText) {
  if (!qaItem || !ocrText) {
    return { valid: false, reason: '缺少 Q&A 或 OCR 資料' }
  }
  
  // 檢查問題和選項的關鍵詞
  const questionText = qaItem.q + ' ' + (qaItem.options || []).join(' ')
  const hasKeywords = checkKeywordHit(questionText, 2)
  if (!hasKeywords) {
    return { valid: false, reason: 'Q&A 關鍵詞命中不足' }
  }
  
  // 檢查 grounding 引用
  if (qaItem.grounding && qaItem.grounding.length > 0) {
    const groundingText = qaItem.grounding.join(' ')
    const similarity = calculateSimilarity(groundingText, ocrText)
    if (similarity < 0.4) {
      return { valid: false, reason: 'Grounding 引用與 OCR 相似度過低' }
    }
  }
  
  return { valid: true }
}

/**
 * 驗證整個結構化資料
 */
export function validateStructuredData(structuredData, ocrText) {
  if (!structuredData || !ocrText) {
    return {
      valid: false,
      reason: '缺少結構化資料或 OCR 文本',
      details: {}
    }
  }
  
  const results = {
    notes: [],
    code: null,
    qa: [],
    overallValid: true,
    confidence: 0
  }
  
  // 驗證筆記
  if (structuredData.notes && Array.isArray(structuredData.notes)) {
    results.notes = structuredData.notes.map(note => {
      const validation = validateNoteItem(note, ocrText)
      if (!validation.valid) {
        results.overallValid = false
      }
      return { ...note, groundingValid: validation.valid, validation }
    })
  }
  
  // 驗證程式碼
  if (structuredData.code) {
    const validation = validateCodeBlock(structuredData.code, ocrText)
    results.code = { ...structuredData.code, groundingValid: validation.valid, validation }
    if (!validation.valid) {
      results.overallValid = false
    }
  }
  
  // 驗證 Q&A
  if (structuredData.qa && Array.isArray(structuredData.qa)) {
    results.qa = structuredData.qa.map(qa => {
      const validation = validateQAItem(qa, ocrText)
      if (!validation.valid) {
        results.overallValid = false
      }
      return { ...qa, groundingValid: validation.valid, validation }
    })
  }
  
  // 計算整體置信度
  const totalItems = results.notes.length + (results.code ? 1 : 0) + results.qa.length
  const validItems = results.notes.filter(n => n.groundingValid).length + 
                    (results.code?.groundingValid ? 1 : 0) + 
                    results.qa.filter(q => q.groundingValid).length
  
  results.confidence = totalItems > 0 ? validItems / totalItems : 0
  results.groundingMatches = validItems
  results.totalItems = totalItems
  
  return results
}

/**
 * 檢查 OCR 文本品質
 */
export function checkOCRQuality(ocrText) {
  if (!ocrText || ocrText.trim().length < 10) {
    return { quality: 'poor', reason: 'OCR 文本過短或為空' }
  }
  
  const keywordHits = checkKeywordHit(ocrText, 1)
  if (!keywordHits) {
    return { quality: 'poor', reason: 'OCR 文本未包含相關關鍵詞' }
  }
  
  const textLength = ocrText.trim().length
  if (textLength < 50) {
    return { quality: 'fair', reason: 'OCR 文本較短，可能影響分析品質' }
  }
  
  return { quality: 'good', reason: 'OCR 文本品質良好' }
}
