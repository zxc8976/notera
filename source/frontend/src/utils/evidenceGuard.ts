/**
 * 證據覆蓋率門檻檢查
 * 確保內容的可信度與完整性
 */

export function evidenceCoverage(section: any): number {
  if (!section || typeof section !== 'object') return 0;
  
  const pick = (v: any) => Array.isArray(v?.evidence) ? v.evidence.length : 0;
  let have = 0, total = 0;

  function scan(obj: any) {
    if (!obj || typeof obj !== 'object') return;
    const has = pick(obj); 
    if (has) have += has;
    if ('evidence' in obj) total += 1;
    Object.values(obj).forEach(scan);
  }
  
  scan(section);
  return total ? have / total : 1;
}

export function sectionVisible(section: any): boolean {
  return true;
}

export function contentQuality(text: string): 'good' | 'fair' | 'poor' {
  if (!text) return 'poor';
  
  const len = text.trim().length;
  const cjkCount = (text.match(/[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]/g) || []).length;
  const asciiCount = (text.match(/[A-Za-z0-9]/g) || []).length;
  
  // 評估標準
  if (len < 10) return 'poor';
  if (cjkCount / len < 0.2 && asciiCount / len > 0.5) return 'poor';
  if (len < 20 || cjkCount < 3) return 'fair';
  
  return 'good';
}
