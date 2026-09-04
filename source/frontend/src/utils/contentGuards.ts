/**
 * 文字清理與內容守門工具
 * 直接解決 OCR 噪音與無意義內容
 */

export function denoiseText(raw: string): string {
  if (!raw) return "";
  let s = raw
    // 折斷奇怪的殘字：多個空白、符號重複
    .replace(/[ \t]{2,}/g, " ")
    .replace(/[—–-]{2,}/g, "—")
    // 去掉無意義的英數殘片（長度=1 且非標點）
    .replace(/(?<=^|[\s、，。；：()（）\[\]{}""''])\w(?=$|[\s、，。；：()（）\[\]{}""''])/g, "")
    // 合併被 OCR 切斷的 latin 片段
    .replace(/([A-Za-z])\s+([A-Za-z])/g, "$1$2")
    // 常見 OCR 噪音：隨機大寫串 + 數字序列
    .replace(/\b[A-Z]{3,}\d{2,}\b/g, "")
    .trim();

  // 若非中日文佔比過低，視為噪音直接清空
  const cj = (s.match(/[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9fff]/g) || []).length;
  const ascii = (s.match(/[A-Za-z0-9]/g) || []).length;
  if (s.length && cj / Math.max(1, s.length) < 0.25 && ascii > cj * 2) return "";
  return s;
}

export function hasMeaningfulText(s?: string): boolean {
  if (!s) return false;
  const t = denoiseText(s);
  if (!t) return false;
  // 過短或只有一兩個詞也當作無意義
  if (t.replace(/\s/g, "").length < 6) return false;
  // 黑名單：避免把「TE YOUTUEE / PhoneWndohs / GOOGe食号…」當內容
  const ban = /(youtub|goog|phone|win(dows|dohs)|ocahos|chalbod|3u?t|5173|te\s*youtu?ee|phonewndohs|googe|食号)/i;
  if (ban.test(t)) return false;
  return true;
}

export function hasItems(arr?: any[]): boolean {
  return Array.isArray(arr) && arr.length > 0;
}

export function shouldRenderSection(section: any): boolean {
  if (!section) return false;
  return true;
}
