import { marked } from 'marked'
import DOMPurifyFactory from 'dompurify'
import katex from 'katex'
import { markedHighlight } from 'marked-highlight'
import hljs from 'highlight.js'
import 'highlight.js/styles/atom-one-dark.css' // Ensure CSS is imported

// Configure marked with highlight.js
marked.use(markedHighlight({
  langPrefix: 'hljs language-',
  highlight(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value;
    } else {
      // Auto-detect language if not specified or unknown
      return hljs.highlightAuto(code).value;
    }
  }
}));

const DEFAULT_TRANSLATE = (key) => key

// 全域關閉 marked 的 mangle / headerIds 以避免 console 警告
marked.setOptions({
  gfm: true,
  breaks: true,
  mangle: false,
  headerIds: false,
})

const maybeExtractTextFromHighlightedHtml = (input = '') => {
  const text = String(input ?? '')
  if (!text) return ''
  const looksHighlighted =
    /<\s*span\b/i.test(text) ||
    /<\/\s*span\s*>/i.test(text) ||
    /\bhljs\b/i.test(text) ||
    /\bhljs-[-\w]+\b/i.test(text) ||
    /&lt;\s*span\b/i.test(text) ||
    /&lt;\s*\/\s*span\s*&gt;/i.test(text) ||
    /&lt;\s*spanclass\b/i.test(text)

  if (!looksHighlighted) return text

  // Browser 환경: HTML -> textContent 로 복원 (entity decode 포함)
  if (typeof window !== 'undefined' && window.document) {
    const div = window.document.createElement('div')
    div.innerHTML = text
    return div.textContent || ''
  }

  // SSR/無 DOM: 保守處理 (僅去除 tag，並解少量常見 entity)
  return text
    .replace(/<\/?span[^>]*>/gi, '')
    .replace(/<\/?code[^>]*>/gi, '')
    .replace(/<\/?pre[^>]*>/gi, '')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&amp;/gi, '&')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
 }

const escapeHtml = (s = '') => String(s ?? '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;')

const unescapeHtmlEntities = (s = '') => String(s ?? '')
  .replace(/&lt;/g, '<')
  .replace(/&gt;/g, '>')
  .replace(/&quot;/g, '"')
  .replace(/&#39;/g, "'")
  .replace(/&amp;/g, '&')

const decodeEscapedMathHtmlBlocks = (html = '') => {
  if (!html) return html
  if (!/&(?:amp;)?lt;/.test(html)) return html

  const decodeOnce = (value = '') => unescapeHtmlEntities(String(value ?? ''))
  const decodeTwice = (value = '') => {
    const once = decodeOnce(value)
    const twice = decodeOnce(once)
    return twice === once ? once : twice
  }

  const patterns = [
    /&(?:amp;)?lt;div[^&]*class=["'][^"']*(math-text-block|math-block|katex)[^"']*["'][\s\S]*?&(?:amp;)?lt;\/div&(?:amp;)?gt;/gi,
    /&(?:amp;)?lt;math\b[\s\S]*?&(?:amp;)?lt;\/math&(?:amp;)?gt;/gi,
    /&(?:amp;)?lt;(mrow|mi|mo|mn|msup|msub|mfrac|msqrt|mtable|mtr|mtd|msubsup|semantics|annotation)\b[\s\S]*?&(?:amp;)?gt;/gi,
  ]

  let output = html
  patterns.forEach((re) => {
    output = output.replace(re, (match) => decodeTwice(match))
  })

  return output
}

const maybeDecodeEscapedMathHtml = (text = '') => {
  const source = String(text || '')
  if (!/&lt;\s*(div|span|math)\b/i.test(source)) return null

  const unescaped = unescapeHtmlEntities(source)
  const hasMathMarkup =
    /class=["'][^"']*(math-text-block|math-block|math-inline|katex)/i.test(unescaped) ||
    /<math\b/i.test(unescaped) ||
    /<(mrow|mi|mo|mn|msup|msub|mfrac|msqrt|mtable|mtr|mtd)\b/i.test(unescaped)

  if (!hasMathMarkup) return null

  if (/<div\b[^>]*class=["'][^"']*math-text-block/i.test(unescaped)) {
    return unescaped
  }

  return `<div class="math-text-block" data-no-enhance="true">${unescaped}</div>`
}

const denoiseText = (raw = '') => {
  if (!raw) return ''
  let s = raw
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/[—–-]{2,}/g, '—')
    .replace(/(?<=^|[\s、，。；：()（）\[\]{}"''])\w(?=$|[\s、，。；：()（）\[\]{}"''])/g, '')
    .replace(/([A-Za-z])\s+([A-Za-z])/g, '$1$2')
    .replace(/\b[A-Z]{3,}\d{2,}\b/g, '')
    .trim()

  const cj = (s.match(/[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9fff]/g) || []).length
  const ascii = (s.match(/[A-Za-z0-9]/g) || []).length
  if (s.length && cj / Math.max(1, s.length) < 0.25 && ascii > cj * 2) return ''
  return s
}

const hasMeaningfulText = (input) => {
  if (!input) return false
  const text = String(input || '')
  const latexLike = /(\$[^$\n]+?\$|\$\$[\s\S]+?\$\$|\\sum|\\frac|\\pi|\\int|\\sqrt|\\begin\{|\\end\{|π|∑|Σ|∞)/.test(text)
  if (latexLike && text.replace(/\s/g, '').length >= 6) return true
  const cleaned = denoiseText(input)
  if (!cleaned) return false
  if (cleaned.replace(/\s/g, '').length < 6) return false
  const ban = /(youtub|goog|phone|win(dows|dohs)|ocahos|chalbod|3u?t|5173|te\s*youtu?ee|phonewndohs|googe|食号)/i
  return !ban.test(cleaned)
}

const cleanHtmlEntities = (str) => str ?? ''

const normalizeLegacyCodeBlocks = (html = '', options = {}) => {
  const createCodeId = typeof options.createCodeId === 'function'
    ? options.createCodeId
    : (() => {
        let counter = 0
        return () => `legacy-code-${Date.now().toString(36)}-${++counter}`
      })()
  if (!html) return ''

  // 簡易字串版（SSR 或無 DOM 環境）
  if (typeof window === 'undefined' || !window.document) {
    return html
      .replace(/<div class="code-block-header">[\s\S]*?<\/div>/gi, '')
      .replace(/<div class="code-block-container">([\s\S]*?)<\/div>/gi, '$1')
      .replace(/<code[^>]*>\s*<code[^>]*>/gi, '<code>')
      .replace(/<\/code>\s*<\/code>/gi, '</code>')
      .replace(/<p>\s*text\s*<\/p>/gi, '')
      .replace(/(?:^|\n)\s*text\s*(?=\n|<)/gi, '')
  }

  const wrapper = document.createElement('div')
  wrapper.innerHTML = html

  // 移除舊版 header/按鈕
  wrapper.querySelectorAll('.code-block-header').forEach((el) => el.remove())
  wrapper.querySelectorAll('.gpt-code-header').forEach((el) => el.remove())
  // 只移除舊版 code-frame 相關的按鈕；不要誤刪新版 `.code-container` 的複製按鈕
  wrapper.querySelectorAll('button.code-frame__copy, button.gpt-copy-btn').forEach((btn) => btn.remove())

  // 展開舊版 code-block-container，保留子內容
  wrapper.querySelectorAll('.code-block-container').forEach((el) => {
    const frag = document.createDocumentFragment()
    while (el.firstChild) {
      frag.appendChild(el.firstChild)
    }
    el.replaceWith(frag)
  })
  wrapper.querySelectorAll('.gpt-code-block').forEach((el) => {
    const frag = document.createDocumentFragment()
    while (el.firstChild) {
      frag.appendChild(el.firstChild)
    }
    el.replaceWith(frag)
  })

  const escapeHtml = (s = '') => s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

  const flattenPreCode = (pre, codeEl) => {
    // 已經是我們自己的 plain-code-block（前端渲染用），不要再轉成 gpt-code-frame（否則會被 fallback CSS 隱藏）
    if (
      pre?.classList?.contains('plain-code-block') ||
      pre?.getAttribute?.('data-no-enhance') === 'true' ||
      pre?.getAttribute?.('data-no-highlight') === 'true'
    ) {
      return
    }

    const codeText = codeEl.textContent || ''
    if (!codeText.trim()) {
      pre.remove()
      return
    }
    const codeId = createCodeId()
    const langMatch = (codeEl.className || '').match(/language-([\w#+-]+)/i)
    const inferred = (langMatch?.[1] || '').trim() || guessCodeLanguage(codeText)
    const lang = inferred || 'text'

    // 統一轉成新版 code-container（避免 `.code-frame` 在 fallback CSS 被隱藏，導致沒有語言/複製鈕）
    const container = document.createElement('div')
    container.className = 'code-container'
    container.setAttribute('data-no-enhance', 'true')

    const header = document.createElement('div')
    header.className = 'code-header'

    const langTag = document.createElement('span')
    langTag.className = 'code-language'
    langTag.textContent = lang

    const copyBtn = document.createElement('button')
    copyBtn.type = 'button'
    copyBtn.className = 'code-copy-btn'
    copyBtn.setAttribute('data-code-id', codeId)
    copyBtn.textContent = '複製'

    header.appendChild(langTag)
    header.appendChild(copyBtn)

    const codeContent = document.createElement('pre')
    codeContent.className = 'code-block plain-code-block'
    codeContent.setAttribute('data-no-enhance', 'true')

    const codeNode = document.createElement('code')
    codeNode.id = codeId
    codeNode.className = `hljs language-${lang}`
    try {
      codeNode.innerHTML = hljs.getLanguage(lang)
        ? hljs.highlight(codeText, { language: lang }).value
        : hljs.highlightAuto(codeText).value
    } catch (_e) {
      codeNode.innerHTML = escapeHtml(codeText)
    }

    codeContent.appendChild(codeNode)
    container.appendChild(header)
    container.appendChild(codeContent)

    pre.replaceWith(container)
  }

  // 重新包裝/展平成舊的 gpt-code-block
  wrapper.querySelectorAll('.gpt-code-block').forEach((block) => {
    const codeEl = block.querySelector('code')
    if (!codeEl) return
    const pre = document.createElement('pre')
    pre.appendChild(codeEl)
    flattenPreCode(pre, codeEl)
    block.replaceWith(pre)
  })

  // 裸露的 pre>code
  wrapper.querySelectorAll('pre').forEach((pre) => {
    if (pre.closest('.code-frame')) return
    const codeEl = pre.querySelector('code')
    if (!codeEl) return
    flattenPreCode(pre, codeEl)
  })

  // 移除空 code
  wrapper.querySelectorAll('code').forEach((code) => {
    if (!code.textContent || !code.textContent.trim()) {
      code.remove()
    }
  })

  // 若出現 code > code 巢狀，展平成單一 code
  wrapper.querySelectorAll('code code').forEach((inner) => {
    const parent = inner.closest('code')
    if (parent) {
      parent.innerHTML = inner.innerHTML
    }
  })

  // 清掉獨立的 "text" 或語言名稱殘留段落/文字節點
  wrapper.querySelectorAll('p, div, span').forEach((node) => {
    const txt = (node.textContent || '').trim().toLowerCase()
    if (txt === 'text' || ['java', 'python', 'cpp', 'c++', 'bash', 'shell'].includes(txt)) {
      node.remove()
    }
  })

  // 移除空的 pre / code-frame（避免出現空白框）
  wrapper.querySelectorAll('pre').forEach((el) => {
    if (!el.textContent || !el.textContent.trim()) el.remove()
  })
  wrapper.querySelectorAll('.code-frame').forEach((frame) => {
    const code = frame.querySelector('code')
    if (!code || !code.textContent || !code.textContent.trim()) {
      frame.remove()
    }
  })
  wrapper.querySelectorAll('div').forEach((el) => {
    if (!el.children.length && !(el.textContent || '').trim()) {
      el.remove()
    }
  })

  // 移除殘留的舊容器（若未被重組）
  wrapper.querySelectorAll('.code-block-container, .gpt-code-block').forEach((el) => el.remove())

  // 解除 math-inline / katex 外層 span，避免文字化
  wrapper.querySelectorAll('span.math-inline').forEach((el) => {
    const parent = el.parentNode
    if (!parent) return
    const frag = document.createDocumentFragment()
    Array.from(el.childNodes).forEach((c) => frag.appendChild(c))
    parent.replaceChild(frag, el)
  })
  wrapper.querySelectorAll('span.katex-html, span.katex-mathml, span.katex').forEach((el) => {
    const parent = el.parentNode
    if (!parent) return
    const frag = document.createDocumentFragment()
    Array.from(el.childNodes).forEach((c) => frag.appendChild(c))
    parent.replaceChild(frag, el)
  })

  return wrapper.innerHTML
}

const generateTopicFromContent = (contentLines) => {
  const text = contentLines.join(' ').toLowerCase()
  if (text.includes('string') && text.includes('stringbuilder')) {
    return '🎯 Java 字串處理：String 與 StringBuilder 的比較與應用'
  }
  if (text.includes('javascript') && text.includes('object')) {
    return '🎯 JavaScript 物件導向程式設計：基礎類別與方法'
  }
  if (text.includes('number') && text.includes('parseint')) {
    return '🎯 JavaScript 數值處理與型別轉換'
  }
  if (text.includes('dom') && text.includes('document')) {
    return '🎯 DOM 操作基礎：文件物件模型與事件處理'
  }
  if (text.includes('equals') && text.includes('comparison')) {
    return '🎯 物件比較：equals() 方法與 == 運算子的差異'
  }
  return '🎯 程式設計概念：物件導向與資料型別處理'
}

const resolvePurifier = () => {
  if (typeof DOMPurifyFactory === 'function') {
    if (typeof window !== 'undefined') {
      return DOMPurifyFactory(window)
    }
    if (typeof globalThis !== 'undefined' && globalThis.window) {
      return DOMPurifyFactory(globalThis.window)
    }
  }
  return DOMPurifyFactory
}

const purifier = resolvePurifier()

const sanitizeHtml = (html, config = {}) => {
  if (purifier && typeof purifier.sanitize === 'function') {
    return purifier.sanitize(html, config)
  }
  if (typeof DOMPurifyFactory.sanitize === 'function') {
    return DOMPurifyFactory.sanitize(html, config)
  }
  return html
}

const CODE_FENCE_SPLIT_REGEX = /(```[\s\S]*?```)/g
const ESCAPED_DOLLAR = /\\\$/g
const PLACEHOLDER = '__KATEX_DOLLAR__'

// 補救 LLM 產生的不完整 code fence：若開頭 ``` 數量為奇數，補一個結尾 ```，避免後面整篇被吃進 code block
const repairBrokenFences = (md = '') => {
  if (!md) return md
  const fenceCount = (md.match(/```/g) || []).length
  if (fenceCount % 2 === 1) {
    return `${md}\n\n\`\`\`\n`
  }
  return md
}

const normalizeFenceIndentation = (md = '') => {
  if (!md) return md
  return md
    .split('\n')
    .map((line) => {
      if (/^\s{4,}```/.test(line)) {
        return line.replace(/^\s+/, '')
      }
      return line
    })
    .join('\n')
}

const normalizeFenceBoundaries = (md = '') => {
  if (!md) return md
  return md
    // text followed by opening fence on same line: xxx```java
    .replace(/([^\n])```([A-Za-z][\w+-]*)(?=\n|$)/g, '$1\n```$2')
    // closing fence glued to section boundary: ```--- / ```##
    .replace(/```(?=(---\s*$|#{1,6}\s+|!\[|<\s*(details|summary|img)\b))/gm, '```\n')
    // closing fence glued to CJK/plain narrative line: ```程式碼分析
    .replace(/```(?=[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9fff])/g, '```\n')
    // closing fence glued to previous text: text```
    .replace(/([^\n])```(?=\n|$)/g, '$1\n```')
}

const normalizeFencePadding = (md = '') => {
  if (!md) return md
  return md
    // avoid accidental blank line immediately after opening fence
    .replace(/```([A-Za-z][\w+-]*)\n{2,}/g, '```$1\n')
    .replace(/```\n{3,}/g, '```\n\n')
}

const rewrapEmptyFences = (md = '') => {
  if (!md) return md
  const lines = md.split('\n')
  const out = []
  const isFence = (line) => /^\s*```(\S*)?\s*$/.exec(line)
  const isSectionBoundary = (line) =>
    /^\s*(?:---|#{1,6}\s+|!\[|<\s*(?:img|details|summary)\b)/.test(line)
  const isLikelyCodeLine = (line) =>
    /[;{}]/.test(line) ||
    /^\s*(import|from|def|class|public|private|protected|return|if|for|while|#include)\b/.test(line)

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]
    const openMatch = isFence(line)
    if (!openMatch) {
      out.push(line)
      continue
    }
    const lang = (openMatch[1] || '').trim()
    // Look for immediate closing fence after optional blank lines
    let j = i + 1
    while (j < lines.length && !lines[j].trim()) j += 1
    const closeMatch = j < lines.length ? isFence(lines[j]) : null
    if (!closeMatch) {
      out.push(line)
      continue
    }
    // Empty fence detected, try to rewrap the following indented/code-like block
    let k = j + 1
    const block = []
    while (k < lines.length) {
      const current = lines[k]
      if (!current.trim()) {
        if (block.length) {
          block.push(current)
          k += 1
          continue
        }
        k += 1
        continue
      }
      if (isFence(current) || isSectionBoundary(current)) break
      if (/^\s{4,}/.test(current) || isLikelyCodeLine(current)) {
        block.push(current)
        k += 1
        continue
      }
      break
    }
    if (block.length >= 2) {
      const dedented = block.map((b) => b.replace(/^\s{4}/, ''))
      out.push(`\`\`\`${lang || 'text'}`)
      out.push(...dedented)
      out.push('```')
      // Skip a trailing closing fence that belonged to the broken block
      if (k < lines.length) {
        const trailing = isFence(lines[k])
        const trailingLang = trailing ? (trailing[1] || '').trim() : ''
        if (trailing && !trailingLang) {
          k += 1
        }
      }
      i = k - 1
      continue
    }
    // If no block to rewrap, just drop the empty fence
    i = j
  }
  return out.join('\n')
}

const dropMathErrorLines = (md = '') => {
  if (!md) return md
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  const errorRe = /(math mode at position|katex parse error|parseerror|expected.*?math|KaTeX parse error)/i
  return segments
    .map((seg) => {
      if (seg.startsWith('```')) return seg
      return seg
        .split('\n')
        .filter((line) => !errorRe.test(line))
        .join('\n')
    })
    .join('')
}

const dropPipeNoiseLines = (md = '') => {
  if (!md) return md
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  const pipeNoise = /^[\s|:-]{4,}$/
  return segments
    .map((seg) => {
      if (seg.startsWith('```')) return seg
      return seg
        .split('\n')
        .filter((line) => !pipeNoise.test(line))
        .join('\n')
    })
    .join('')
}

// 補救「fence 數量為偶數但仍然配對錯亂」：
// - 例如某段 ```java 開了但少了結尾 ```，後面的 ```java 會被當成 closing，導致後續章節全進 code block。
// - 規則：在 fence 內遇到「帶語言的 ```xxx」時，把它視為新開塊，先自動補上一個 closing ```。
// - 或在 fence 內遇到明顯的章節分隔（---、#、![）時，自動關閉 fence。
const repairMispairedFences = (md = '') => {
  if (!md) return md
  const lines = md.split('\n')
  const out = []
  let inFence = false
  let fenceLines = 0

  const fenceMatch = (line) => /^\s*```(\S*)\s*$/.exec(line)
  const isLikelySectionBoundary = (line) =>
    /^\s*---\s*$/.test(line) ||
    /^\s*#{1,6}\s+/.test(line) ||
    /^\s*(?:[-*]|\d+\.)\s+/.test(line) || // list item
    /^\s*\|.*\|\s*$/.test(line) || // table row
    /^\s*!\[/.test(line) ||
    /^\s*<\s*(details|summary|img)\b/i.test(line)
  const isLikelyNarrativeInsideFence = (line) => {
    const raw = String(line || '')
    const trimmed = raw.trim()
    if (!trimmed) return false
    // code comment lines are still code; don't auto-close on them
    if (/^\s*(\/\/|#|--)\s*/.test(trimmed)) return false
    // bold/markdown-ish lines should never appear inside code
    if (/^\*\*[^*].+\*\*\s*$/.test(trimmed)) return true
    if (/^__[^_].+__\s*$/.test(trimmed)) return true
    // if a language tag appears as a standalone line inside a fence, it's almost always stray narration
    if (/^(java|python|javascript|typescript|cpp|c\+\+|c#|csharp|sql|bash|shell|plaintext)\s*$/i.test(trimmed)) return true
    // markdown-ish patterns that should never be inside code
    if (/^\s*(#{1,6}\s+|>+\s+|[-*]\s+|\d+\.\s+|\|.+\|)\s*/.test(trimmed)) return true
    // long CJK-heavy narrative line (likely swallowed text), low symbol density
    const cjk = (trimmed.match(/[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9fff]/g) || []).length
    const sym = (trimmed.match(/[;{}()[\]=<>]/g) || []).length
    if (trimmed.length >= 60 && cjk / Math.max(1, trimmed.length) > 0.55 && sym < 3) return true
    return false
  }

  for (const line of lines) {
    const m = fenceMatch(line)
    if (m) {
      const lang = (m[1] || '').trim()
      if (!inFence) {
        inFence = true
        fenceLines = 0
        out.push(line)
        continue
      }

      // inFence === true
      // 1) ` ```lang ` 出現在 code fence 中，極大概率代表上一段 fence 少了 closing。
      if (lang) {
        out.push('```')
        // 立刻重新開啟新 fence（保留原本 lang）
        inFence = true
        fenceLines = 0
        out.push(line)
        continue
      }

      // 2) 正常 closing fence
      inFence = false
      fenceLines = 0
      out.push('```')
      continue
    }

    // 在 code fence 內遇到章節/圖片/標題，通常是 fence 配對錯了，先自動關閉。
    if (inFence) {
      fenceLines += 1
      if (fenceLines >= 2 && (isLikelySectionBoundary(line) || isLikelyNarrativeInsideFence(line))) {
        out.push('```')
        inFence = false
        fenceLines = 0
      }
    }

    out.push(line)
  }

  if (inFence) {
    out.push('```')
  }

  return out.join('\n')
}

// 將「同一行內夾帶的程式碼」抽出並包成 fenced code，避免被當成一般段落或被 HTML/DOMPurify 吃掉（例如 Map<String,...>）
const extractInlineCodeFences = (md = '') => {
  if (!md) return md
  const lines = md.split('\n')
  const out = []
  let inFence = false

  const fenceLine = (line) => /^\s*```/.test(line)
  const codeStartPatterns = [
    /\b(java|python|cpp|c\+\+|javascript|typescript|bash|shell)\s+(?=(public|private|protected|class|import|from|def|#include|function|const|let|var)\b)/i,
    /\b(public|private|protected)\s+class\s+\w+/i,
    /\bimport\s+[\w.]+/i,
    /\bdef\s+\w+\s*\(/i,
    /\bfunction\s+\w+\s*\(/i,
  ]
  const normalizeLangLabel = (text = '') => {
    const trimmed = text.trimStart()
    const labelMatch = /^(text|plaintext|java|python|cpp|c\+\+|javascript|typescript|bash|shell)[:：-]?\s+/i.exec(trimmed)
    if (!labelMatch) return { lang: null, body: text }
    const lang = labelMatch[1].toLowerCase()
    const body = trimmed.slice(labelMatch[0].length)
    return { lang, body }
  }
  const guessLang = (body = '') => {
    if (/public\s+class|System\.out|package\s+\w+/i.test(body)) return 'java'
    if (/^#include\b|std::/m.test(body)) return 'cpp'
    if (/^\s*def\s+\w+/m.test(body)) return 'python'
    if (/\bfunction\s+\w+|\bconst\b|\blet\b|\bvar\b/i.test(body)) return 'javascript'
    return 'text'
  }

  for (const line of lines) {
    if (fenceLine(line)) {
      inFence = !inFence
      out.push(line)
      continue
    }
    if (inFence) {
      out.push(line)
      continue
    }

    const raw = String(line || '')
    if (raw.length < 80) {
      out.push(raw)
      continue
    }

    let idx = null
    for (const re of codeStartPatterns) {
      const m = re.exec(raw)
      if (m && (idx === null || m.index < idx)) idx = m.index
    }

    if (idx === null) {
      out.push(raw)
      continue
    }

    // 若從行首就開始像程式碼（例如 "java public class ..." 或 "public class ..."），允許直接抽出
    const allowNoCue = idx === 0
    const prefix = raw.slice(Math.max(0, idx - 80), idx)
    const cue = /[:：]\s*$/.test(prefix) || /(程式碼|代碼|code|示例|範例|例|實作|實現)/i.test(prefix)
    if (!cue && !allowNoCue) {
      out.push(raw)
      continue
    }

    const before = raw.slice(0, idx).trimEnd()
    const tail = raw.slice(idx).trim()
    if (tail.length < 60) {
      out.push(raw)
      continue
    }

    const tailLooksCodeish =
      /(class\s+\w+|public\s+|private\s+|protected\s+|def\s+\w+|function\s+\w+|#include|import\s+[\w.]+|System\.out|console\.log|return\s+)/i.test(tail) ||
      (tail.match(/[;{}()[\]=<>]/g) || []).length >= 6

    if (!tailLooksCodeish) {
      out.push(raw)
      continue
    }

    const normalized = normalizeLangLabel(tail)
    let lang = normalized.lang || guessLang(tail)
    let body = String(normalized.body ?? tail).trim()

    if (lang === 'c++') lang = 'cpp'
    if (lang === 'plaintext') lang = 'text'

    if (before) out.push(before)
    out.push('')
    out.push(`\`\`\`${lang}`)
    out.push(body)
    out.push('```')
    out.push('')
  }

  return out.join('\n')
}

const guessCodeLanguage = (codeText = '') => {
  const text = String(codeText || '')
  if (
    /^\s*(package|import)\s+[\w.]+;\s*$/m.test(text) ||
    /\bpublic\s+class\b/.test(text) ||
    /\bpublicclass\b/i.test(text) ||
    /\bSystem\.out\.println\b/.test(text)
  ) {
    return 'java'
  }
  if (/^\s*def\s+\w+\s*\(/m.test(text) || /\bprint\(/.test(text)) return 'python'
  if (/^\s*#include\b/m.test(text) || /\bstd::\w+/.test(text)) return 'cpp'
  if (/\b(function\s+\w+|\bconst\b|\blet\b|\bvar\b)\b/.test(text) || /\bconsole\.log\b/.test(text)) return 'javascript'
  if (/^\s*SELECT\b|\bFROM\b|\bWHERE\b/im.test(text)) return 'sql'
  if (/^\s*<\w+[\s>]/m.test(text) && /<\/\w+>\s*$/m.test(text)) return 'html'
  return 'text'
}

const normalizeLatexBackslashes = (text = '') => {
  // LLM 常把 LaTeX 指令寫成 \\sum / \\pi（多一個反斜線），導致 KaTeX 無法正常解析
  // 只在「看起來像指令」時縮減：\\[a-zA-Z] -> \[a-zA-Z]
  return String(text || '').replace(/\\\\+([a-zA-Z])/g, '\\$1')
}

const normalizeMathSymbols = (text = '') => {
  if (!text) return ''
  return String(text || '')
    .replace(/π/g, '\\pi')
    .replace(/∑/g, '\\sum')
    .replace(/Σ/g, '\\sum')
    .replace(/×/g, '\\times ')
    .replace(/⋅/g, '\\cdot ')
}

const splitBlockquoteLine = (line = '') => {
  const match = /^(\s*>\s+)([\s\S]*)$/.exec(line)
  if (!match) return null
  return { prefix: match[1], body: match[2] }
}

const normalizeMarkdownSyntax = (md = '') => {
  if (!md) return md
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  return segments
    .map((seg) => {
      if (seg.startsWith('```')) return seg
      return seg
        // 修復 LLM 產生的「# # 標題」或「## # 標題」等破損 heading（把多段 # 合併為單一層級）
        .replace(/^(#{1,6})(?:\s+#{1,6})+\s+(.+)$/gm, (m, _first, title) => {
          const total = (m.match(/#/g) || []).length
          const level = Math.min(6, Math.max(1, total))
          return `${'#'.repeat(level)} ${String(title || '').trim()}`
        })
        // heading 必須補空白：###標題 => ### 標題（避免被當成普通文字）
        .replace(/(^|\n)(#{1,6})(?=\S)(?!include\b)/g, '$1$2 ')
        // 修復標題黏住的程式碼圍欄：### 程式碼分析```java => 分行
        .replace(/(^|\n)(#{1,6}\s*[^\n]*?)\s*```(\w+)?/gim, '$1$2\n```$3')
        // 確保標題起始在新行
        .replace(/([^\n])\s*(#{2,6}\s+)/g, '$1\n$2')
        // 移除標題尾巴黏住的語言標籤：### 程式碼分析java => ### 程式碼分析
        .replace(/(^|\n)(#{1,6}\s*[^\n]*?)(java|python|cpp|c\+\+|javascript|typescript|bash|shell)\s*$/gim, '$1$2')
        // 移除標題內容前的殘留 # 符號
        .replace(/(^|\n)(#{1,6})\s+#\s+(.+)$/gm, '$1$2 $3')
    })
    .join('')
}


const dropOcrNoiseLines = (md = '') => {
  if (!md) return md
  const lines = md.split('\n')
  const out = []
  for (const line of lines) {
    const trimmed = line.trim()
    // 連續頁碼/行號（例：274 275 276 277...）
    if (/^(\d{2,4}\s+){3,}\d{2,4}$/.test(trimmed)) continue
    // 連續頁碼/行號（逗號分隔或帶註解）
    if (/^(\d{2,4}\s*[,，]\s*){2,}\d{2,4}(\s*[,，]\s*\d{2,4})*(\s*（[^）]*）|\s*\([^)]*\))?\s*$/u.test(trimmed)) continue
    // 單獨的頁碼（避免誤殺：只移除在空白區域單獨一行的純數字）
    if (/^\d{2,4}$/.test(trimmed) && (out.length === 0 || !out[out.length - 1].trim())) continue
    // 常見 OCR 噪音標記
    if (/^[■□●○◆◇]\s*問題\s*\d+\s*$/i.test(trimmed)) continue
    // 重複括號/符號噪音（例如 ((((((( )
    if (/^[()（）\[\]{}<>]{6,}$/.test(trimmed)) continue
    out.push(line)
  }
  return out.join('\n')
}

const unquoteBacktickWrappedMath = (md = '') => {
  if (!md) return md
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  return segments
    .map((seg) => {
      if (seg.startsWith('```')) return seg
      return seg
        // `$$...$$` -> $$...$$
        .replace(/`(\$\$[\s\S]*?\$\$)`/g, '$1')
        // `$...$` -> $...$
        .replace(/`(\$[^$\n]+?\$)`/g, '$1')
    })
    .join('')
}

const convertInlineCodeMathToLatex = (md = '') => {
  if (!md) return md
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  const mathLike = (text) =>
    /(\\sum|\\frac|\\pi|\\times|\\cdot|\\text\{|\\begin\{|\\end\{|\\int|\\sqrt|π|∑|Σ|∞|×|⋅)/.test(text) ||
    (/[=_^]/.test(text) && /\\[a-zA-Z]+/.test(text))

  return segments
    .map((seg) => {
      if (seg.startsWith('```')) return seg
      return seg.replace(/`([^`\n]{4,})`/g, (m, body) => {
        const inner = String(body || '').trim()
        // 已經是 $...$ 或 $$...$$ 的就不要動
        if ((inner.startsWith('$$') && inner.endsWith('$$')) || (inner.startsWith('$') && inner.endsWith('$'))) {
          return inner
        }
        // 只轉換「看起來像數學」的 inline code；一般 code term (Map, List...) 不動
        if (!mathLike(inner)) return m
        // 避免 $ 破壞：先 escape
        const normalized = normalizeMathSymbols(normalizeLatexBackslashes(inner))
        const escaped = normalized.replace(/\$/g, '\\$')
        return `$${escaped}$`
      })
    })
    .join('')
}

const hasLatexTextCommand = (text = '') =>
  /\\text\{[^}]*\}|\\mathrm\{[^}]*\}|\\operatorname\{[^}]*\}/.test(text)

const normalizeFenceLines = (md = '') => {
  if (!md) return md
  // Strip trailing comments or labels after a fence language.
  return md.replace(/(^|\n)```(\w+)\s+(?:\/\/|#|\/\*).*$/gim, '$1```$2')
}

const wrapBareLatexLines = (md = '') => {
  if (!md) return md
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  const latexCmd = /(\\sum|\\frac|\\pi|\\times|\\cdot|\\text\{|\\begin\{|\\end\{|\\int|\\sqrt|\\mathbb|\\mathcal|\\mid|\\gamma|\\left|\\right|π|∑|Σ|∞)/

  return segments
    .map((seg) => {
      if (seg.startsWith('```')) return seg
      return seg
        .split('\n')
        .map((line) => {
          const blockquote = splitBlockquoteLine(line)
          const targetLine = blockquote ? blockquote.body : line
          const trimmed = targetLine.trim()
          if (!trimmed) return line
          if (trimmed.startsWith('#')) return line
          if (trimmed.startsWith('|')) return line // table
          if (/^[-*]\s+/.test(trimmed)) return line // list item
          if (trimmed.includes('$')) return line
          if (!latexCmd.test(trimmed)) return line

          const normalizedTrimmed = normalizeMathSymbols(normalizeLatexBackslashes(trimmed))
          // 避免把一般文字中的反斜線誤判成 LaTeX
          const mathy = /[=_^]/.test(normalizedTrimmed) || /\\(sum|frac|pi|times|cdot|text|int|sqrt|begin|end)\b/.test(normalizedTrimmed)
          if (!mathy) return line

          // 只包住「整行都像公式」的情況
          if (normalizedTrimmed.length < 10) return line
          const wrapped = `$$${normalizedTrimmed}$$`
          return blockquote ? `${blockquote.prefix}${wrapped}` : wrapped
        })
        .join('\n')
    })
    .join('')
}

// list item 內的 LaTeX（例如 "- 公式：\\sum ... = 1"）盡量包成 $...$，避免整段被當普通文字而不渲染
const wrapLatexInListItems = (md = '') => {
  if (!md) return md
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  const latexCmd = /(\\sum|\\frac|\\pi|\\times|\\cdot|\\text\{|\\begin\{|\\end\{|\\int|\\sqrt|\\mathbb|\\mathcal|\\mid|\\gamma|\\left|\\right|π|∑|Σ|∞)/

  const looksSafeMath = (s = '') => {
    const t = String(s || '').trim()
    if (!t) return false
    if (!latexCmd.test(t)) return false
    const cjk = (t.match(/[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9fff]/g) || []).length
    if (cjk / Math.max(1, t.length) > 0.25 && !hasLatexTextCommand(t)) return false
    return /[=_^]/.test(t) || /\\[a-zA-Z]+/.test(t)
  }

  return segments
    .map((seg) => {
      if (seg.startsWith('```')) return seg
      return seg
        .split('\n')
        .map((line) => {
          const blockquote = splitBlockquoteLine(line)
          const targetLine = blockquote ? blockquote.body : line
          const trimmed = String(targetLine || '').trim()
          if (!trimmed) return line
          if (trimmed.includes('$')) return line
          const listMatch = /^(\s*(?:[-*]|\d+\.)\s+)([\s\S]+)$/.exec(targetLine)
          if (!listMatch) return line
          const prefix = listMatch[1]
          const rest = listMatch[2]
          if (!latexCmd.test(rest)) return line

          const lastColon = Math.max(rest.lastIndexOf(':'), rest.lastIndexOf('：'))
          if (lastColon >= 0) {
            const before = rest.slice(0, lastColon + 1)
            const tail = normalizeLatexBackslashes(rest.slice(lastColon + 1).trim())
            if (!looksSafeMath(tail)) return line
            const escaped = tail.replace(/\$/g, '\\$')
            return `${prefix}${before} $${escaped}$`
          }

          // 沒有冒號時：只在整個 rest 看起來幾乎都是數學式時才包
          const normalizedRest = normalizeLatexBackslashes(rest)
          if (!looksSafeMath(normalizedRest)) return line
          const escaped = normalizedRest.trim().replace(/\$/g, '\\$')
          const wrapped = `${prefix}$${escaped}$`
          return blockquote ? `${blockquote.prefix}${wrapped}` : wrapped
        })
        .join('\n')
    })
    .join('')
}

// 將「看起來像整行公式」但未用 $/$$ 包住的 LaTeX 行補上 $$...$$
// 例：\\sum_{a\\in A} \\pi(a|s)=1
const wrapBareLatexDisplayLines = (md = '') => {
  if (!md) return md
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  const latexCmd = /(\\sum|\\frac|\\pi|\\times|\\cdot|\\text\{|\\begin\{|\\end\{|\\int|\\sqrt|\\mathbb|\\mathcal|\\mid|\\gamma|\\left|\\right|π|∑|Σ|∞)/
  return segments
    .map((seg) => {
      if (seg.startsWith('```')) return seg
      return seg
        .split('\n')
        .map((line) => {
          const blockquote = splitBlockquoteLine(line)
          const targetLine = blockquote ? blockquote.body : line
          const trimmed = String(targetLine || '').trim()
          if (!trimmed) return line
          if (trimmed.includes('$')) return line
          if (trimmed.startsWith('#')) return line
          if (/^\s*(?:[-*]|\d+\.)\s+/.test(trimmed)) return line
          if (trimmed.startsWith('|')) return line
          if (!latexCmd.test(trimmed)) return line

          // 避免誤包中文敘述行：CJK 比例太高就跳過
      const cjk = (trimmed.match(/[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9fff]/g) || []).length
      const cjkRatio = cjk / Math.max(1, trimmed.length)
      if (cjkRatio > 0.25 && !hasLatexTextCommand(trimmed)) return line

          // 必須具有「數學感」：包含 {}() 或運算符號或下標/上標
          const mathy = /[=_^]|\\[a-zA-Z]+/.test(trimmed) && /[{}()]/.test(trimmed)
          if (!mathy && trimmed.length < 18) return line

          const normalized = normalizeMathSymbols(normalizeLatexBackslashes(trimmed))
          const escaped = normalized.replace(/\$/g, '\\$')
          const wrapped = `$$${escaped}$$`
          return blockquote ? `${blockquote.prefix}${wrapped}` : wrapped
        })
        .join('\n')
    })
    .join('')
}

const isNarrativeFence = (lang = '', body = '') => {
  const text = String(body || '')
  const cjkCount = (text.match(/[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9fff]/g) || []).length
  const asciiCount = (text.match(/[A-Za-z0-9]/g) || []).length
  const symbolCount = (text.match(/[;{}()[\]=<>]/g) || []).length
  const length = text.length || 1
  const cjkRatio = cjkCount / length
  const symbolRatio = symbolCount / length
  const codeKeywordHit = /(class\s+\w+|public\s+|private\s+|protected\s+|def\s+\w+|function\s+\w+|#include|import\s+\w+|package\s+\w+|console\.log|System\.out|return\s+)/i.test(text)
  const markdowny = /(^|\n)\s*(#{2,6}\s+|[-*]\s+|\|.+\|)/.test(text) || /\*\*.+\*\*/.test(text)
  const hasCodeLines = /(^|\n)\s*(if|for|while|switch|case|try|catch)\b/.test(text) || /[{};]\s*$/.test(text)
  const langLower = String(lang || '').toLowerCase()
  const lines = text.split('\n').filter((line) => line.trim().length)
  const codeLineCount = lines.filter((line) => /[;{}]|\b(class|public|private|protected|def|import|void|return|package)\b/.test(line)).length
  const codeLineRatio = codeLineCount / Math.max(1, lines.length)
  const narrativeOverride = (markdowny || cjkRatio > 0.55) && symbolRatio < 0.12 && codeLineRatio < 0.25
 
  // 真的是程式碼就不解開
  if ((codeKeywordHit || hasCodeLines) && !narrativeOverride) return false
  if (narrativeOverride) return true
  // 如果是 markdown 標題/列表大量出現在 code fence 裡，通常是 LLM 把講義塞進來
  if (markdowny && cjkRatio > 0.4 && symbolRatio < 0.14) return true
  // 大量 CJK 且符號密度低：視為敘述
  if (cjkRatio > 0.6 && symbolRatio < 0.12) return true
  if (cjkCount > asciiCount * 1.5 && symbolCount < 8) return true
 
  // 特定語言標籤（java/py/js...）也可能被誤用；在上述條件成立時允許解開
  if (langLower && cjkRatio > 0.65 && symbolRatio < 0.12) return true
  return false
}

// 若 fenced code 內容其實是敘述文（即使標了 ```java```），則解開為普通文字，避免整段排版變成 code wall
const unwrapNarrativeFences = (md = '') => {
  if (!md) return md
  const fenceRegex = /```([a-zA-Z0-9_-]+)?\s*\n([\s\S]*?)```/g
  return md.replace(fenceRegex, (_m, lang = '', body = '') => {
    if (!body) return _m
    if (isNarrativeFence(lang, body)) {
      return body.trim()
    }
    return _m
  })
}

const createNoteHeading = (variant, text) => {
  const cleanVariant = (variant || 'default').toString().replace(/[^\w-]/g, '') || 'default'
  const title = String(text || '')
  const isJapaneseHeading = /(日文|日本語|原文)/.test(title)
  const jpClass = isJapaneseHeading ? ' note-heading--jp' : ''
  const langAttr = isJapaneseHeading ? ' lang="ja"' : ''
  return `<h2 class="note-heading note-heading--${cleanVariant}${jpClass}"${langAttr}>${title}</h2>`
}

const enhanceJapaneseSections = (html = '') => {
  if (!html) return html
  try {
    const doc = new DOMParser().parseFromString(html, 'text/html')
    const headings = Array.from(doc.querySelectorAll('h1.note-heading, h2.note-heading, h3.note-heading'))
    headings.forEach((heading) => {
      const headingText = (heading.textContent || '').trim()
      if (!/(日文|日本語|原文)/.test(headingText)) return
      heading.classList.add('note-heading--jp')
      heading.setAttribute('lang', 'ja')

      const wrapper = doc.createElement('div')
      wrapper.className = 'jp-section'
      wrapper.setAttribute('lang', 'ja')

      let node = heading.nextSibling
      while (node) {
        if (node.nodeType === 1 && /H[1-3]/.test(node.tagName) && node.classList.contains('note-heading')) {
          break
        }
        const next = node.nextSibling
        wrapper.appendChild(node)
        node = next
      }

      if (wrapper.childNodes.length) {
        heading.parentNode.insertBefore(wrapper, node)
      }
    })
    return doc.body.innerHTML
  } catch (error) {
    console.warn('[markdownRenderer] Japanese section enhance failed:', error)
    return html
  }
}

const renderLatexSegment = (expr = '', displayMode = false) => {
  if (!expr) return ''
  try {
    const html = katex.renderToString(expr.trim(), {
      displayMode,
      throwOnError: true,
      strict: 'ignore' // 忽略非 LaTeX 字元警告，避免中文/全形符號刷屏
    })
    return displayMode
      ? `<div class="math-block">${html}</div>`
      : `<span class="math-inline">${html}</span>`
  } catch (error) {
    console.warn('[markdownRenderer] KaTeX render failed:', error?.message)
    const fallback = escapeHtml(expr.trim())
    return displayMode
      ? `<div class="math-block math-block--fallback">${fallback}</div>`
      : `<span class="math-inline math-inline--fallback">${fallback}</span>`
  }
}

export const renderMathExpressions = (markdown = '') => {
  if (!markdown) return markdown

  const segments = markdown.split(CODE_FENCE_SPLIT_REGEX)
  return segments
    .map(segment => {
      if (segment.startsWith('```')) {
        return segment
      }

      let processed = segment.replace(ESCAPED_DOLLAR, PLACEHOLDER)

      processed = processed.replace(/\$\$([\s\S]+?)\$\$/g, (_match, expr) => renderLatexSegment(expr, true))
      processed = processed.replace(/\$([^$\n]+?)\$/g, (_match, expr) => renderLatexSegment(expr, false))

      return processed.replace(new RegExp(PLACEHOLDER, 'g'), '\\$')
    })
    .join('')
}

export const stripNoisyTextLabels = (md = '') => {
  if (!md) return ''
  return md
    .split('\n')
    .map((line) => {
      let processed = line
      
      // 1. Remove lines that are JUST language names (common hallucination)
      // e.g. "python", "java", "c++" on their own line
      if (/^\s*(python|java|cpp|c\+\+|javascript|typescript|bash|shell|text)\s*$/i.test(processed)) {
        return ''
      }

      // 2. Remove "text" if it is the only thing on the line
      if (/^\s*text[:：]?\s*$/i.test(processed)) return ''

      // 2.1 Remove bullet-only "text" label
      if (/^\s*[-*•]\s*text[:：-]?\s*$/i.test(processed)) return ''

      // 3. Handle "text" followed by specific chars (comments, braces, etc) WITHOUT space
      // e.g. "text//", "text{", "text("
      if (/^\s*text\s*(?=\/\/|[{([<])/i.test(processed)) {
          processed = processed.replace(/^\s*text\s*/i, '')
      }

      // 4. Handle language labels followed by code keywords
      const langLabels = 'text|python|java|cpp|c\\+\\+|javascript|typescript|bash|shell'
      const codeKeywords = 'import|class|public|private|protected|def|void|enum|#include|package|const|let|var'
      
      const prefixRegex = new RegExp(`^\\s*(${langLabels})[:：]?\\s+(?=(${codeKeywords}))`, 'i')
      if (prefixRegex.test(processed)) {
          processed = processed.replace(prefixRegex, '')
      }
      
      // 5. General "text " prefix removal (fallback)
      // Be careful not to remove "text" from "textbook" or "text processing"
      // Only remove if followed by space/colon AND we are reasonably sure it's a label
      // For now, in this domain, "text " at start of line is 99% a label.
      processed = processed.replace(/^(\s*)text[:：]?\s+(?=[^\s])/i, '$1')

      // 6. Handle "text //" specifically (no space)
      if (/^\s*text\s*\/\//i.test(processed)) {
          processed = processed.replace(/^\s*text\s*/i, '')
      }

      // 7. AGGRESSIVE FALLBACK: Remove "text" followed by ANY non-word char if it looks like code
      // This catches "text //", "text {", "text (", "text [", "text <" even if previous rules missed
      if (/^\s*text\s*[^a-z0-9\s]/i.test(processed)) {
          // Double check it's not "text-align" or something
          if (!/^\s*text-[a-z]/i.test(processed)) {
             processed = processed.replace(/^\s*text\s*/i, '')
          }
      }

      return processed
    })
    .join('\n')
}

export const formatFlattenedCode = (md) => {
  if (!md) return ''
  // Process line by line to avoid the "whole file has newlines" bug
  return md.split('\n').map(line => {
      let processed = line
      
      // Skip HTML lines (start with <) to avoid breaking math/layout
      if (/^\s*</.test(processed)) return processed

      // 1. Fix: "text // comment public class" -> "// comment \n public class"
      // This handles the case where "text" was removed but the line is still flattened
      // We look for a comment // followed eventually by a code keyword
      if (processed.length > 80 && /\/\/.*(public|class|enum|interface|void|int|def|import)/.test(processed)) {
          processed = processed.replace(/(\/\/.*?)(\s+public|\s+class|\s+enum|\s+interface|\s+void|\s+int|\s+def|\s+import)/g, '$1\n$2')
      }

      // 2. Fix: Flattened Java/C structures
      // Use word boundaries \b to avoid matching "point" as "int" or "floating" as "float"
      // Also ensure we don't match CSS styles like "float: left" (which has colon, not space usually, but just in case)
      if (processed.length > 80 && /\b(public class|enum State|void main|struct|interface|int|String|boolean|double|float)\s/.test(processed)) {
          // Heuristic: if it contains multiple semicolons or braces, it might be flattened
          // AND it must look like code (not just text with semicolons)
          // We check for at least 3 semicolons OR 2 braces
          if ((processed.match(/;/g) || []).length > 2 || (processed.match(/\{/g) || []).length > 1) {
              // Double check: ensure it's not just a long text with semicolons (like HTML entities)
              // If it has "int " but also "&lt;" or "&nbsp;", it's likely HTML/Text
              if (!/&[a-z]+;/.test(processed)) {
                  processed = processed
                    .replace(/;\s*/g, ';\n')
                    .replace(/\{\s*/g, '{\n')
                    .replace(/\}\s*/g, '\n}\n')
                    .replace(/\n\s*\n/g, '\n')
              }
          }
      }

      // 3. Fix: Flattened Python "text import random ..."
      // The "text" part should be handled by cleanMarkdown, but if not:
      if (/^text\s+import/.test(processed)) {
          processed = processed.replace(/^text\s+/, '')
      }
      
      // 4. Fix: Python flattened code (def, class, if, return on one line)
      if (processed.length > 50 && /import\s+\w+/.test(processed) && /def\s+\w+/.test(processed)) {
         processed = processed
            .replace(/(\s+def\s+)/g, '\n$1')
            .replace(/(\s+class\s+)/g, '\n$1')
            .replace(/(\s+if\s+__name__)/g, '\n$1')
            .replace(/(\s+return\s+)/g, '\n$1')
      }

      return processed
  }).join('\n')
}

// 將以 text 標籤開頭且疑似程式碼/數學的區塊包成 fenced code，避免殘留「text」字樣
// eslint-disable-next-line no-unused-vars
const wrapTextLabeledBlocks = (md = '') => {
  const lines = md.split('\n')
  const out = []
  let inFence = false

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (/^\s*```/.test(line)) {
      inFence = !inFence
      out.push(line)
      continue
    }

    if (inFence) {
      out.push(line)
      continue
    }

    const match = /^\s*text[:：-]?\s*(.*)$/i.exec(line)
    if (match) {
      const block = []
      const first = match[1] || ''
      if (first) block.push(first)

      let j = i + 1
      while (j < lines.length) {
        const next = lines[j]
        if (!next.trim()) break
        if (/^\s*```/.test(next)) break
        if (/^\s*#/.test(next)) break
        block.push(next)
        j++
      }

      out.push('```')
      out.push(block.join('\n'))
      out.push('```')
      i = j - 1
      continue
    }

    out.push(line)
  }

  return out.join('\n')
}

const stripHallucinatedHtml = (md) => {
  if (!md) return ''

  // NUCLEAR OPTION: Aggressively strip common HTML tags (both raw and escaped)
  // The LLM occasionally returns KaTeX/Highlight.js HTML that ends up rendered as text.
  // We drop them entirely so the markdown stays readable instead of showing tag soup.

  const tagList = '(?:span|div|p|a|code|pre|br|strong|em|b|i|u|mark|table|thead|tbody|tr|td|th|ul|ol|li|figure|figcaption|section|article|header|footer|nav)'
  const rawTagRegex = new RegExp(`<\\/?${tagList}[^>]*>`, 'gi')
  const escapedTagRegex = new RegExp(`&lt;\\/?${tagList}[^&]*?&gt;`, 'gi')

  let working = md
    // 1. Strip common tags (raw + escaped)
    .replace(rawTagRegex, '')
    .replace(escapedTagRegex, '')

    // 2. Strip specific KaTeX/MathJax wrappers if they sneak through
    .replace(/<div[^>]*class=["'][^"']*(katex|katex-html|katex-mathml)[^"']*["'][^>]*>/gi, '')
    .replace(/&lt;div[^>]*class=["'][^"']*(katex|katex-html|katex-mathml)[^"']*["'][^>]*&gt;/gi, '')

    // 3. Remove style/script blocks that were escaped
    .replace(/&lt;style[^>]*&gt;[\s\S]*?&lt;\/style&gt;/gi, '')
    .replace(/&lt;script[^>]*&gt;[\s\S]*?&lt;\/script&gt;/gi, '')

    // 4. Normalize common HTML entities that otherwise bloat the text
    .replace(/&nbsp;/gi, ' ')

  // 5. Clean up empty or noisy gaps left behind
  working = working
    .replace(/\n{3,}/g, '\n\n')
    .replace(/[ \t]{3,}/g, ' ')

  return working
}

const stripSpanArtifacts = (html = '') => {
  return html
    // Escaped span / spanclass wrappers
    .replace(/&lt;\/?span[^>]*&gt;/gi, '')
    .replace(/<\/?spanclass[^>]*>/gi, '')
    .replace(/&lt;\/?spanclass[^>]*&gt;/gi, '')
    // Stray "spanclass=..." fragments
    .replace(/spanclass\s*=\s*["'][^"']*["']>?/gi, '')
    .replace(/&lt;spanclass\s*=\s*["'][^"']*["'][^>]*&gt;/gi, '')
    // Bare spanclass words leaking into text
    .replace(/spanclass[^<\s>]*/gi, '')
}

// 移除被轉義或原始輸出的 highlight.js/span 標籤，避免殘留在頁面上
const stripResidualHighlightSpans = (html = '') => {
  return html
    // 成對的轉義 hljs/span
    .replace(/&lt;span[^>]*class="h?l?js-[^"]*"[^>]*&gt;([\s\S]*?)&lt;\/span&gt;/gi, '$1')
    // 成對的錯字 spanclass（少了空白）
    .replace(/&lt;spanclass[^>]*&gt;([\s\S]*?)&lt;\/spanclass&gt;/gi, '$1')
    .replace(/<spanclass[^>]*>([\s\S]*?)<\/spanclass>/gi, '$1')
    // 已被轉義的 span/hljs 標籤
    .replace(/&lt;\/?span[^>]*class="h?l?js-[^"]*"[^>]*&gt;/gi, '')
    .replace(/&lt;\/?code[^>]*class="h?l?js[^"]*"[^>]*&gt;/gi, '')
    .replace(/&lt;\/?spanclass[^>]*&gt;/gi, '')
    // 單獨出現的 spanclass="..."（缺少起始符號）
    .replace(/spanclass\s*=\s*["'][^"']*["']>?/gi, '')
    .replace(/&lt;spanclass\s*=\s*["'][^"']*["'][^>]*&gt;/gi, '')
}

const normalizePipeTables = (md = '') => {
  if (!md) return md
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  const isDivider = (line) =>
    /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line)
  const isListLine = (line) => /^\s*(?:[-*]|\d+\.)\s+/.test(line)
  const isTableRow = (line) => {
    const trimmed = String(line || '').trim()
    if (!trimmed) return false
    if (isListLine(trimmed)) return false
    if (!trimmed.includes('|')) return false
    const pipeCount = (trimmed.match(/\|/g) || []).length
    return pipeCount >= 2
  }
  const buildDivider = (line) => {
    let trimmed = String(line || '').trim()
    if (trimmed.startsWith('|')) trimmed = trimmed.slice(1)
    if (trimmed.endsWith('|')) trimmed = trimmed.slice(0, -1)
    const columnCount = Math.max(2, trimmed.split('|').length)
    return `| ${Array(columnCount).fill('---').join(' | ')} |`
  }

  return segments
    .map((seg) => {
      if (seg.startsWith('```')) return seg
      const lines = seg.split('\n')
      const out = []
      for (let i = 0; i < lines.length; i += 1) {
        const line = lines[i]
        if (isTableRow(line) && !isDivider(line)) {
          let j = i + 1
          while (j < lines.length && !lines[j].trim()) j += 1
          const next = j < lines.length ? lines[j] : ''
          if (next && isTableRow(next) && !isDivider(next)) {
            out.push(line)
            out.push(buildDivider(line))
            continue
          }
        }
        out.push(line)
      }
      return out.join('\n')
    })
    .join('')
}

const dedupeConsecutiveParagraphs = (md = '') => {
  if (!md) return md
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  return segments
    .map((seg) => {
      if (seg.startsWith('```')) return seg
      const parts = seg.split(/\n{2,}/)
      const out = []
      let prevKey = ''
      for (const part of parts) {
        const trimmed = part.trim()
        if (!trimmed) {
          out.push(part)
          prevKey = ''
          continue
        }
        const key = trimmed.replace(/\s+/g, ' ').toLowerCase()
        if (key.length > 20 && key === prevKey) {
          continue
        }
        out.push(part)
        prevKey = key
      }
      return out.join('\n\n')
    })
    .join('')
}

const stripOrphanTableDividers = (md = '') => {
  if (!md) return md
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  const stripQuote = (line = '') => {
    const match = /^(\s*>\s+)([\s\S]*)$/.exec(line)
    return match ? { prefix: match[1], body: match[2] } : { prefix: '', body: line }
  }
  const isDivider = (line) =>
    /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line)
  const isLonePipe = (line) => /^\s*\|?\s*\|?\s*$/.test(line)
  const isListLine = (line) => /^\s*(?:[-*]|\d+\.)\s+/.test(line)
  const isTableRow = (line) => {
    const trimmed = String(line || '').trim()
    if (!trimmed) return false
    if (isListLine(trimmed)) return false
    if (!trimmed.includes('|')) return false
    const pipeCount = (trimmed.match(/\|/g) || []).length
    return pipeCount >= 2 && !isDivider(trimmed)
  }

  return segments
    .map((seg) => {
      if (seg.startsWith('```')) return seg
      const lines = seg.split('\n')
      const out = []
      for (let i = 0; i < lines.length; i += 1) {
        const line = lines[i]
        const { body } = stripQuote(line)
        const bodyTrimmed = body.trim()

        if (isLonePipe(bodyTrimmed)) {
          continue
        }

        if (isDivider(bodyTrimmed)) {
          let prev = i - 1
          while (prev >= 0 && !lines[prev].trim()) prev -= 1
          let next = i + 1
          while (next < lines.length && !lines[next].trim()) next += 1
          const prevRow = prev >= 0 ? stripQuote(lines[prev]).body : ''
          const nextRow = next < lines.length ? stripQuote(lines[next]).body : ''
          if (!isTableRow(prevRow) || !isTableRow(nextRow)) {
            continue
          }
        }
        out.push(line)
      }
      return out.join('\n')
    })
    .join('')
}

const wrapLatexAfterColon = (md = '') => {
  if (!md) return md
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  const latexCmd = /(\\sum|\\frac|\\pi|\\times|\\cdot|\\text\{|\\begin\{|\\end\{|\\int|\\sqrt|\\mathbb|\\mathcal|\\mid|\\gamma|\\left|\\right|π|∑|Σ|∞)/
  const looksSafeMath = (s = '') => {
    const t = String(s || '').trim()
    if (!t) return false
    if (!latexCmd.test(t)) return false
    const cjk = (t.match(/[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9fff]/g) || []).length
    if (cjk / Math.max(1, t.length) > 0.25 && !hasLatexTextCommand(t)) return false
    return /[=_^]/.test(t) || /\\[a-zA-Z]+/.test(t)
  }
  const hasCodeComment = (line = '') => /(^|[^:])\/\/|\/\*|\*\//.test(line)
  const labelRegex = /^(.*?(?:公式|式|equation|eq\.?)\s*(?:\([^)]+\))?\s*)(.+)$/i

  return segments
    .map((seg) => {
      if (seg.startsWith('```')) return seg
      return seg
        .split('\n')
        .map((line) => {
          const blockquote = splitBlockquoteLine(line)
          const targetLine = blockquote ? blockquote.body : line
          const trimmed = String(targetLine || '').trim()
          if (!trimmed) return line
          if (trimmed.includes('$')) return line
          if (trimmed.startsWith('#')) return line
          if (trimmed.startsWith('|')) return line
          if (/^\s*(?:[-*]|\d+\.)\s+/.test(trimmed)) return line
          if (hasCodeComment(line)) return line
          if (!latexCmd.test(trimmed)) return line
          const lastColon = Math.max(trimmed.lastIndexOf(':'), trimmed.lastIndexOf('：'))
          if (lastColon < 0) {
            const labelMatch = labelRegex.exec(trimmed)
            if (!labelMatch) return line
            const labelPrefix = labelMatch[1].trimEnd()
            const tail = normalizeLatexBackslashes(labelMatch[2].trim())
          if (!looksSafeMath(tail)) return line
          const escaped = tail.replace(/\$/g, '\\$')
          const wrapped = `${labelPrefix} $${escaped}$`
          return blockquote ? `${blockquote.prefix}${wrapped}` : wrapped
          }
          const prefix = trimmed.slice(0, lastColon + 1)
          const tail = normalizeMathSymbols(normalizeLatexBackslashes(trimmed.slice(lastColon + 1).trim()))
          if (!looksSafeMath(tail)) return line
          const escaped = tail.replace(/\$/g, '\\$')
          const wrapped = `${prefix} $${escaped}$`
          return blockquote ? `${blockquote.prefix}${wrapped}` : wrapped
        })
        .join('\n')
    })
    .join('')
}

const dedupeConsecutiveLines = (md = '') => {
  if (!md) return md
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  return segments
    .map((seg) => {
      if (seg.startsWith('```')) return seg
      const lines = seg.split('\n')
      const out = []
      let prevKey = ''
      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) {
          out.push(line)
          prevKey = ''
          continue
        }
        const key = trimmed
          .replace(/\s+/g, ' ')
          .replace(/\$/g, '')
          .toLowerCase()
        if (key.length > 20 && key === prevKey) {
          continue
        }
        out.push(line)
        prevKey = key
      }
      return out.join('\n')
    })
    .join('')
}

const wrapLatexCommandLines = (md = '') => {
  if (!md) return md
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  const hasLatexCommands = (line = '') => {
    const matches = line.match(/\\[a-zA-Z]+/g) || []
    if (matches.length < 2) return false
    return /[=_^]/.test(line) || /\\(sum|frac|cdot|times|left|right|mathbb|mathcal|gamma|int|sqrt|begin|end)\b/.test(line)
  }
  return segments
    .map((seg) => {
      if (seg.startsWith('```')) return seg
      return seg
        .split('\n')
        .map((line) => {
          const blockquote = splitBlockquoteLine(line)
          const targetLine = blockquote ? blockquote.body : line
          const trimmed = targetLine.trim()
          if (!trimmed) return line
          if (trimmed.includes('$')) return line
          if (trimmed.startsWith('#')) return line
          if (trimmed.startsWith('|')) return line
          if (/^\s*(?:[-*]|\d+\.)\s+/.test(trimmed)) return line
          if (!hasLatexCommands(trimmed)) return line
          const normalized = normalizeMathSymbols(normalizeLatexBackslashes(trimmed))
          const escaped = normalized.replace(/\$/g, '\\$')
          const wrapped = `$$${escaped}$$`
          return blockquote ? `${blockquote.prefix}${wrapped}` : wrapped
        })
        .join('\n')
    })
    .join('')
}

const dedentNarrativeLines = (md = '') => {
  if (!md) return md
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  const codeish = (line = '') =>
    /[;{}]/.test(line) ||
    /\b(class|public|private|protected|def|import|return|System\.out|console\.log)\b/.test(line)

  return segments
    .map((seg) => {
      if (seg.startsWith('```')) return seg
      return seg
        .split('\n')
        .map((line) => {
          if (!/^\s{4,}/.test(line)) return line
          const trimmed = line.trim()
          if (!trimmed) return ''
          if (codeish(trimmed)) return line
          return line.replace(/^\s{4}/, '')
        })
        .join('\n')
    })
    .join('')
}

const collapseRepeatedPipeLines = (md = '') => {
  if (!md) return md
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  const isRepeating = (cells, unitSize) => {
    if (unitSize <= 0 || cells.length < unitSize * 3) return false
    for (let i = 0; i < cells.length; i += 1) {
      if (cells[i] !== cells[i % unitSize]) return false
    }
    return true
  }

  return segments
    .map((seg) => {
      if (seg.startsWith('```')) return seg
      return seg
        .split('\n')
        .map((line) => {
          const trimmed = line.trim()
          if (!trimmed || !trimmed.includes('|') || trimmed.length < 200) return line
          const cells = trimmed
            .split('|')
            .map((cell) => cell.trim().replace(/\s+/g, ' '))
            .filter((cell) => cell)
          if (cells.length < 8) return line
          const unique = new Set(cells)
          if (unique.size > 4) return line

          let unitSize = 0
          for (let size = 1; size <= Math.min(6, Math.floor(cells.length / 2)); size += 1) {
            if (isRepeating(cells, size)) {
              unitSize = size
              break
            }
          }
          if (!unitSize) return line

          const unit = cells.slice(0, unitSize).join(' | ')
          return unit
        })
        .join('\n')
    })
    .join('')
}

const dedupeConsecutiveCodeLines = (md = '') => {
  if (!md) return md
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  return segments
    .map((seg) => {
      if (!seg.startsWith('```')) return seg
      const lines = seg.split('\n')
      if (lines.length < 3) return seg
      const out = [lines[0]]
      let prev = null
      for (let i = 1; i < lines.length - 1; i += 1) {
        const line = lines[i]
        const trimmed = line.trim()
        if (prev === line && trimmed.length >= 16) {
          continue
        }
        out.push(line)
        prev = line
      }
      out.push(lines[lines.length - 1])
      return out.join('\n')
    })
    .join('')
}

const stripMathTextBlocks = (md) => {
  if (!md) return ''
  let result = md
  const startRegex = /<div class="math-text-block"[^>]*>/i
  let maxIterations = 10 // Reduced from 50 to prevent hang

  while (maxIterations-- > 0) {
    const match = startRegex.exec(result)
    if (!match) break

    const startIndex = match.index
    const openTagLength = match[0].length
    const contentStartIndex = startIndex + openTagLength

    // Scan for balanced </div>
    let depth = 1
    let currentIndex = contentStartIndex
    let contentEndIndex = -1

    const tagRegex = /<\/?div/gi
    tagRegex.lastIndex = currentIndex
    
    while (depth > 0) {
      const tagMatch = tagRegex.exec(result)
      if (!tagMatch) {
        // If we can't find a closing tag, assume the rest of the string is content
        // This handles truncated output or malformed HTML
        contentEndIndex = result.length
        break
      }

      if (tagMatch[0].toLowerCase().startsWith('<div')) {
        depth++
      } else {
        depth--
      }

      if (depth === 0) {
        contentEndIndex = tagMatch.index
      }
    }

    // If we found a block (or forced end of string)
    if (contentEndIndex !== -1) {
      const content = result.substring(contentStartIndex, contentEndIndex)
      
      // Wrap logic
      let replacement = content
      const trimmed = content.trim()
      const isFenced = trimmed.startsWith('```')
      
      // Check for code-like features
      // const looksLikeCode = /[;{}=]/.test(content) || /\b(class|public|def|import|void|int|float|return|#include)\b/.test(content)
      
      // Check for math-like features (LaTeX commands or delimiters)
      // We want to avoid wrapping actual math in text fences
      // const looksLikeMath = /(\$\$?|\\begin|\\frac|\\sum|\\int|\\pi|\\alpha|\\beta|\\gamma)/.test(content)
      
      // Always strip HTML tags that might be hallucinated inside the block (e.g. highlight.js artifacts)
      // This prevents "garbled text" where HTML tags are treated as text and escaped.
      // Use the shared aggressive stripper
      let cleanContent = stripHallucinatedHtml(trimmed)
      
      // Fallback for other tags if not caught by stripHallucinatedHtml (which focuses on spans/katex)
      if (!isFenced) {
         cleanContent = cleanContent.replace(/<\/?(div|p|code|pre|br|strong|em|b|i)[^>]*>/gi, '')
      }

      // Re-evaluate looksLikeCode on cleaned content to avoid false positives from HTML tags
      const looksLikeCode = /[;{}=]/.test(cleanContent) || /\b(class|public|def|import|void|int|float|return|#include)\b/.test(cleanContent)
      
      // Check for math-like features
      const looksLikeMath = /(\$\$?|\\begin|\\frac|\\sum|\\int|\\pi|\\alpha|\\beta|\\gamma)/.test(cleanContent)
      
      // If the block is mostly narrative, do not wrap as code
  const cjkCount = (cleanContent.match(/[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9fff]/g) || []).length
  const symbolCount = (cleanContent.match(/[;{}()[\]=<>]/g) || []).length
  const cjkRatio = cjkCount / Math.max(1, cleanContent.length)
  const narrativeBlock = cjkRatio > 0.5 && symbolCount < 8
  const hasListMarkers = /(^|\n)\s*[-*]\s+/.test(cleanContent)
  const hasMarkdownHeadings = /(^|\n)\s*#{1,4}\s+/.test(cleanContent)
  const hasInlineMath = /(\$[^$]+\$|\\\(|\\\))/i.test(cleanContent)
  const hasLongParagraph = cleanContent.length > 240
  const treatAsNarrative = narrativeBlock || hasListMarkers || hasMarkdownHeadings || (hasInlineMath && hasLongParagraph)

  if (!isFenced && looksLikeCode && !looksLikeMath && !treatAsNarrative) {
     replacement = '\n```text\n' + cleanContent + '\n```\n'
  } else {
     replacement = cleanContent
  }
      
      // </div> length is 6. If we hit end of string, it's 0.
      const closeTagLength = (contentEndIndex === result.length) ? 0 : 6
      
      result = result.substring(0, startIndex) + replacement + result.substring(contentEndIndex + closeTagLength)
    } else {
       // Should not happen given the logic above, but just in case
       break
    }
  }
  
  // Final safety sweep: if any math-text-block tags remain (e.g. due to regex mismatch or other issues), force remove them
  if (/<div class="math-text-block"[^>]*>/i.test(result)) {
      result = result.replace(/<div class="math-text-block"[^>]*>/gi, '').replace(/<\/div>/gi, '')
  }
  
  return result
}

export const cleanMarkdown = (md) => {
  if (!md) return ''
  // Remove BOM if present
  let working = md.replace(/^\uFEFF/, '')

  // 先修復 fence 配對錯亂（避免整個章節被吞進 code block）
  working = normalizeFenceIndentation(working)
  working = rewrapEmptyFences(working)
  working = repairMispairedFences(working)
  working = repairBrokenFences(working)
  // 修正 fence 開頭行出現註解或雜訊（```java // ...）
  working = normalizeFenceLines(working)
  // 修復「同一行內」開啟的 code fence（例如："# 標題 ```java"），避免整段被吞進 code block
  // 只處理帶語言標籤的 opening fence，避免誤改到 closing fence。
  working = working.replace(/(^|\n)([^\n]*?)```(\w+)[ \t]*/g, '$1$2\n```$3\n')
  // 修復「同一行內」關閉 fence（例如："...```## 下一段"），避免後續全被當成 code
  // 僅在 ``` 後面是非語言標籤字元時才拆行，避免誤傷 ```java / ```text 這類 opening fence。
  working = working.replace(/```[ \t]*([^A-Za-z0-9_\n][^\n]*)(?=\n|$)/g, '```\n$1')
  // 修復六個反引號造成的 code fence 失配（常見 LLM 產物）
  working = working.replace(/```{3,}/g, '```')
  // 修復三反引號後面接標題/分隔線（常見: ```**說明** 或 ```---）
  working = working.replace(/```\s*(?=(#{1,6}\s|\*\*|---))/g, '```\n')
  // 再把「同一行夾帶的 code」抽成 fenced code，避免被當段落或被 HTML 吃掉
  working = extractInlineCodeFences(working)
  // 先把被反引號包住的 $/$$ 公式釋放出來（避免被誤判為 code）
  working = unquoteBacktickWrappedMath(working)
  // 轉換「被反引號包住的數學式」回到 KaTeX 可處理的形式
  working = convertInlineCodeMathToLatex(working)
  // 修復常見 markdown 語法問題（### 無空格 / 標題尾巴黏 java）
  working = normalizeMarkdownSyntax(working)
  // 修復缺少分隔線的 pipe 表格，避免表格語法無法渲染
  working = normalizePipeTables(working)
  // 移除孤立的分隔線（|---|---|）避免變成雜訊
  working = stripOrphanTableDividers(working)
  // 移除非程式碼區的多餘縮排，避免被 Markdown 誤判成 code block
  working = dedentNarrativeLines(working)
  // 移除 KaTeX/Math 解析錯誤殘留文字
  working = dropMathErrorLines(working)
  // 移除只有分隔線符號的雜訊行
  working = dropPipeNoiseLines(working)
  // 將冒號後的 LaTeX 片段包成 $...$，避免公式以純文字顯示
  working = wrapLatexAfterColon(working)
  // 將未包裹的 LaTeX 指令行包成 $$...$$
  working = wrapLatexCommandLines(working)
  // 過濾 OCR 行號/頁碼噪音
  working = dropOcrNoiseLines(working)
  // 壓縮重複的 pipe 片段（避免單行大量重複）
  working = collapseRepeatedPipeLines(working)
  // 去除連續重複行（避免公式或敘述重複輸出）
  working = dedupeConsecutiveLines(working)

  // --- AGGRESSIVE CLEANING START (Enhanced v3) ---
  // We use global regexes to catch "text" artifacts that might be inline or at start of lines
  
  // 1. Remove "text" followed by "//" (comments) anywhere
  // Matches: "text //", "text//", "\ntext //", "text\u200B//"
  working = working.replace(/(^|\n|\s)text[\s\u200B]*\/\//gi, '$1//')

  // 2. Remove "text" followed by code keywords (import, public, class, etc.)
  // Matches: "text import", "text public", "text class"
  working = working.replace(/(^|\n|\s)text[\s\u200B]+(?=import|from|def|class|public|void|int|enum|struct|interface)/gi, '$1')

  // 3. Remove "text" followed by data structure starts
  // Matches: "text {", "text [", "text <digit>:"
  working = working.replace(/(^|\n|\s)text[\s\u200B]*(?=[{\[])/gi, '$1')
  working = working.replace(/(^|\n|\s)text[\s\u200B]+(?=\d+:)/gi, '$1')

  // 3.5 Remove leading "text " label at line start (殘留純文字標籤)
  working = working.replace(/(^|\n)\s*text[:：]?\s+(?=\S)/gi, '$1')
  // 3.6 Remove leading "text -" style labels
  working = working.replace(/(^|\n)\s*text\s*[-–—]\s*(?=\S)/gi, '$1')
  // 3.7 Remove text 前綴於數學/LaTeX 行
  const textMathPrefix = new RegExp('(^|\\n)\\s*text\\s+(?=\\\\begin|\\\\end|\\\\pi|\\\\sum|\\\\frac|\\\\\\[|\\\\\\(|math)', 'gi')
  working = working.replace(textMathPrefix, '$1')

  // 3.7.5 Remove hallucinated HTML (KaTeX/Highlight.js artifacts)
  // This must run BEFORE stripMathTextBlocks and wrapCodeLikeBlocks
  working = stripSpanArtifacts(stripResidualHighlightSpans(stripHallucinatedHtml(working)))

  // 3.8 Remove hallucinated "math-text-block" wrapper around code
  // The LLM sometimes hallucinates our internal HTML structure. We must strip it to allow code formatting to work.
  // We use a robust parser to handle nested divs and wrap content in fences if needed.
  working = stripMathTextBlocks(working)

  // 3.8 Remove bullet + text 標籤
  working = working.replace(/(^|\n)\s*[-*•]\s*text[:：-]?\s+(?=\S)/gi, '$1')
  // 3.9 Remove行首 "text:" 或 "text-"（即便後面緊接內容）
  working = working.replace(/(^|\n)\s*text\s*[:：-]\s*(?=\S)/gi, '$1')

  // 4. Remove "text" followed by "math" or latex markers
  working = working.replace(/(^|\n|\s)text[\s\u200B]*(?=\$\$?|\\)/gi, '$1')
  // 4.1 移除行首 text: / text- 標籤
  working = working.replace(/(^|\n)\s*text\s*[:：-]\s*/gi, '$1')

  // --- AGGRESSIVE CLEANING END ---

  working = stripNoisyTextLabels(working)
  // 移除連續重複段落，避免 LLM 重複輸出
  working = dedupeConsecutiveParagraphs(working)
  
  // 嘗試修復壓扁的程式碼
  working = formatFlattenedCode(working)
  // 最終收斂：修正 fence 與章節邊界黏在一起的情況
  working = normalizeFenceBoundaries(working)
  working = normalizeFencePadding(working)
  // 去除 code fence 內連續重複行（常見於 OCR/LLM 的重複）
  working = dedupeConsecutiveCodeLines(working)
  // 將仍殘留的 text 標籤區塊改包成 fenced code -> 移除此步驟，避免誤傷數學公式或正常文本
  // working = wrapTextLabeledBlocks(working)
  return working
}

// 斷行過長文字，但保留 code fence 內內容不動
const breakOverlongLines = (md = '', limit = 160) => {
  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
  const breakLine = (line) => {
    if (line.length <= limit) return line
    return line
      .replace(/([。！？；;!?])/g, '$1\n')
      .replace(/([•●◦◉☆★◆◇▪️▫️▪︎◦⚠️🔑📌✅💡👉➤▶️▸►])/g, '\n$1 ')
  }
  return segments
    .map(seg => {
      // Skip code fences
      if (seg.startsWith('```')) return seg
      
      // Split by display math ($$...$$) to protect them
      const parts = seg.split(/(\$\$[\s\S]+?\$\$)/g)
      return parts
        .map((part, index) => {
          // Skip display math blocks (odd indices after split)
          if (part.startsWith('$$') && part.endsWith('$$')) return part
          // Break long lines only in non-math content
          return part.split('\n').map(breakLine).join('\n')
        })
        .join('')
    })
    .join('')
}

// 若 text fenced block 內容幾乎都是中日文字，解開圍欄回到純文字，避免被當作程式碼
const unwrapCjkTextFences = (md = '') => {
  const fenceRegex = /```(?:text)?\s*\n([\s\S]*?)```/g
  return md.replace(fenceRegex, (m, body = '') => {
    const cjkCount = (body.match(/[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9fff]/g) || []).length
    const asciiCount = (body.match(/[A-Za-z0-9_;{}()[\]=+\-*/<>$\\]/g) || []).length
    // 如果內容明顯是程式碼（有關鍵字或符號密度高），避免解開圍欄造成排版壓扁
    const codeKeywordHit = /(class\s+\w+|public\s+|private\s+|protected\s+|def\s+\w+|function\s+\w+|#include|import\s+\w+|package\s+\w+|console\.log|System\.out|return\s+)/i.test(body)
    const codeSymbolCount = (body.match(/[;{}()[\]=<>]/g) || []).length
    const codeish = codeKeywordHit || codeSymbolCount >= Math.max(4, body.split('\n').length)
    if (codeish) {
      return m
    }
    // 若主要是中日文且程式符號極少，就解除圍欄
    if (cjkCount > asciiCount * 1.2) {
      return body.trim()
    }
    return m
  })
}

export const renderNoteMarkdown = (
  markdown,
  { translate = DEFAULT_TRANSLATE, measure = false } = {}
) => {
  if (!markdown || typeof markdown !== 'string') {
    return {
      html: '',
      diagnostics: {
        injectedButtons: 0,
        codeBlocks: 0,
        renderMs: 0,
        warnings: ['Input markdown is empty or invalid'],
      },
    }
  }

  const startedAt = performance?.now ? performance.now() : Date.now()
  const diagnostics = {
    injectedButtons: 0,
    codeBlocks: 0,
    renderMs: 0,
    warnings: [],
  }

  try {
    const rawMarkdown = markdown
    const hasStructuredHeading = /(^|\n)#{1,6}\s*(?:(?:Chapter|章節|章节)\s*\d+|第\s*\d+\s*章)/m.test(rawMarkdown)
    const hasImageMarker = /!\[[^\]]*\]\(/.test(rawMarkdown) || /<img\s/i.test(rawMarkdown)
    const isStructuredNote = hasStructuredHeading && hasImageMarker

    markdown = repairBrokenFences(repairMispairedFences(markdown))
    markdown = unwrapCjkTextFences(unwrapNarrativeFences(markdown))

    // 如果輸入是 HTML，把 <br>/<p>/<div> 轉換為換行並去除其他標籤，避免整段擠成一行
    let normalized = markdown
    if (!isStructuredNote && /<\s*(p|div|span|br)[^>]*>/i.test(normalized)) {
      normalized = normalized
        .replace(/<br\s*\/?>/gi, '\n')
        .replace(/<\/(p|div|section|article|header|footer|li|ul|ol|h[1-6]|table|tr)>/gi, '\n')
        .replace(/<\/p>/gi, '\n')
        .replace(/<[^>]+>/g, '')
    }

    // Apply aggressive markdown cleaning (LLM hallucination fix)
    if (!isStructuredNote) {
      normalized = cleanMarkdown(normalized)

      // 若行數少且單行過長，或平均行寬過高，強制依標點斷行，避免「文字牆」
      const lines = normalized.split('\n')
      const longestLine = lines.reduce((m, l) => Math.max(m, l.trim().length), 0)
      const avgLen = lines.reduce((s, l) => s + l.trim().length, 0) / Math.max(lines.length, 1)
      if (lines.length < 20 && (longestLine > 180 || avgLen > 120)) {
        normalized = normalized
          .replace(/([。！？；;!?])\s*/g, '$1\n')
          .replace(/([•●◦◉☆★◆◇▪️▫️▪︎◦⚠️🔑📌✅💡👉➤▶️▸►])/g, '\n$1 ')
          .replace(/\n{3,}/g, '\n\n')
      }

      markdown = breakOverlongLines(normalized)
    } else {
      markdown = normalized
    }

    let codeBlockCounter = 0
    const nextCodeId = () => `code-${Date.now().toString(36)}-${++codeBlockCounter}`

    // 將「math \begin{aligned} ... \end{aligned}」樣式直接轉為 math 區塊
    const convertBareAligned = (md) => {
      return md.replace(/^\s*math\s+(\\begin\{aligned\}[\s\S]*?\\end\{aligned\})/gim, (_m, body) => {
        // Strip hallucinated HTML before rendering math
        const cleanBody = stripHallucinatedHtml(body)
        const rendered = renderMathExpressions(`$$${cleanBody}$$`)
        return `\n<div class="math-text-block" data-no-enhance="true">${rendered}</div>\n`
      })
    }

    // 也處理沒有 math 前綴、或殘留 text 標籤的 aligned 區塊
    const convertLooseAligned = (md) => {
      return md.replace(/^\s*(?:text\s+)?(\\begin\{aligned\}[\s\S]*?\\end\{aligned\})/gim, (_m, body) => {
        // Strip hallucinated HTML before rendering math
        const cleanBody = stripHallucinatedHtml(body)
        const rendered = renderMathExpressions(`$$${cleanBody}$$`)
        return `\n<div class="math-text-block" data-no-enhance="true">${rendered}</div>\n`
      })
    }

    // 先將 math/latex 圍欄直接轉為 math 區塊，避免被當作程式碼
    const convertMathFences = (md) => {
      const fenceRegex = /```(?:math|latex|tex)\s*\n([\s\S]*?)```/g
      return md.replace(fenceRegex, (_m, body) => {
        // Strip hallucinated HTML before rendering math
        const cleanBody = normalizeLatexBackslashes(stripHallucinatedHtml(body))
        const wrapped = cleanBody.includes('$$') ? cleanBody : `$$\n${cleanBody}\n$$`
        const rendered = renderMathExpressions(wrapped)
        return `\n<div class="math-text-block" data-no-enhance="true">${rendered}</div>\n`
      })
    }

    // 將 \( \), \[ \] 轉成 $...$ / $$...$$ 以便 KaTeX 處理
    const convertInlineDelimiters = (md) => {
      return md
        .replace(/\\\[(.+?)\\\]/gs, (_m, expr) => `$$${expr}$$`)
        .replace(/\\\((.+?)\\\)/gs, (_m, expr) => `$${expr}$`)
        .replace(/<span class="math-inline">([\s\S]*?)<\/span>/gi, (_m, inner) => inner)
    }

    // 將「看起來像程式碼」但未用圍欄包住的連續行，強制包成 fenced code（但跳過大量中日文字的段落）
const wrapCodeLikeBlocks = (md) => {
  if (!md) return md

  const segments = md.split(CODE_FENCE_SPLIT_REGEX)
    const maybeCode = (block) => {
      const text = String(block || '')
      const cjkCount = (text.match(/[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9fff]/g) || []).length
      const asciiCount = (text.match(/[A-Za-z0-9_;{}()[\]=+\-*/<>$\\]/g) || []).length
      const symbolCount = (text.match(/[;{}()[\]=<>]/g) || []).length
      const codeKeywordHit = /(class\s+\w+|public\s+|private\s+|protected\s+|function\s+\w+|def\s+\w+|#include|import\s+\w+|package\s+\w+|System\.out|console\.log)/i.test(text)
      const cjkRatio = cjkCount / Math.max(1, text.length)
      const containsMarkdown = /(^|\n)\s*(#{1,6}\s+|[-*]\s+|\d+\.\s+|>+\s+|\|.+\||!\[|---\s*$)/m.test(text)
      if (containsMarkdown) return false
      if (/(<img|<math|\\begin\{aligned\}|math-block)/i.test(text)) return false
      if (cjkRatio > 0.45 && symbolCount < 6 && !codeKeywordHit) return false

      const lines = text.split('\n').filter((line) => line.trim().length)
      const codeLineCount = lines.filter((l) => /\b(class|public|private|protected|def|import|#include|return|if|for|while)\b/.test(l) || /[;{}]/.test(l)).length
      const codeLineRatio = codeLineCount / Math.max(1, lines.length)
      const hasClass = /public\s+class\s+\w+/i.test(text)
      const hasImports = /^(import\s+\w+|\s*#include)/im.test(text)
      const manySemicolons = (text.match(/;/g) || []).length >= 3
      const hasBraces = /\{[^}]*\}/.test(text)
      const looksLikeCode = (codeKeywordHit || hasClass || hasImports) && (codeLineRatio >= 0.45 || symbolCount >= 12 || manySemicolons || hasBraces)
      const tooLong = text.length > 1500
      if (!looksLikeCode || tooLong) return false
      return true
    }

  const normalizeLangLabel = (text = '') => {
    const trimmed = text.trimStart()
    const labelMatch = /^(text|plaintext|java|python|cpp|c\+\+|javascript|typescript|bash|shell)[:：-]?\s+/i.exec(trimmed)
    if (!labelMatch) return { lang: null, body: text }
    const lang = labelMatch[1].toLowerCase()
    const body = trimmed.slice(labelMatch[0].length)
    return { lang, body }
  }

  const detectInlineCodeTail = (block) => {
    const text = String(block || '')
    if (!text.trim()) return null
    if (text.includes('```')) return null

    const patterns = [
      /\b(java|python|cpp|c\+\+|javascript|typescript|bash|shell)\s+(?=(public|private|protected|class|import|from|def|#include|function|const|let|var)\b)/i,
      /\b(public|private|protected)\s+class\s+\w+/i,
      /\bimport\s+[\w.]+/i,
      /\bdef\s+\w+\s*\(/i,
      /\bfunction\s+\w+\s*\(/i,
    ]

    let best = null
    for (const re of patterns) {
      const m = re.exec(text)
      if (m && (best === null || m.index < best)) best = m.index
    }

    if (best === null) return null

    const prefix = text.slice(Math.max(0, best - 80), best)
    const cue = /[:：]\s*$/.test(prefix) || /(程式碼|代碼|code|示例|範例|例|實作|實現)/i.test(prefix)
    if (!cue) return null

    const tail = text.slice(best).trim()
    if (tail.length < 60) return null

    const tailLooksCodeish =
      /(class\s+\w+|public\s+|private\s+|protected\s+|def\s+\w+|function\s+\w+|#include|import\s+[\w.]+|System\.out|console\.log|return\s+)/i.test(tail) ||
      (tail.match(/[;{}()[\]=<>]/g) || []).length >= 6

    if (!tailLooksCodeish) return null

    return {
      before: text.slice(0, best).trimEnd(),
      code: tail,
    }
  }

  const wrapBlocksInSegment = (segment) => {
    const blocks = segment.split(/\n{2,}/)
    const wrapped = blocks.flatMap((b) => {
      const inline = detectInlineCodeTail(b)
      if (inline) {
        const normalized = normalizeLangLabel(inline.code)
        let lang = normalized.lang || 'text'
        let body = String(normalized.body ?? inline.code).trim()

        // 嘗試猜語言：含 "class" 用 java，含 "#include" 用 cpp，含 "def " 用 python
        if (!normalized.lang || lang === 'text' || lang === 'plaintext') {
          if (/public\s+class|System\.out|package\s+\w+/i.test(body)) lang = 'java'
          else if (/^#include\b|std::/m.test(body)) lang = 'cpp'
          else if (/^\s*def\s+\w+/m.test(body)) lang = 'python'
        }

        // 統一 lang 名稱（避免 marked/hljs 不認）
        if (lang === 'c++') lang = 'cpp'
        if (lang === 'plaintext') lang = 'text'

        const out = []
        if (inline.before) out.push(inline.before)
        out.push(`\`\`\`${lang}\n${body}\n\`\`\``)
        return out
      }

      if (maybeCode(b)) {
        const normalized = normalizeLangLabel(b)
        let lang = normalized.lang || 'text'
        let body = String(normalized.body ?? b).trim()

        // 嘗試猜語言：含 "class" 用 java，含 "#include" 用 cpp，含 "def " 用 python
        if (!normalized.lang || lang === 'text' || lang === 'plaintext') {
          if (/public\s+class|System\.out|package\s+\w+/i.test(body)) lang = 'java'
          else if (/^#include\b|std::/m.test(body)) lang = 'cpp'
          else if (/^\s*def\s+\w+/m.test(body)) lang = 'python'
        }

        // 統一 lang 名稱（避免 marked/hljs 不認）
        if (lang === 'c++') lang = 'cpp'
        if (lang === 'plaintext') lang = 'text'

        return [`\`\`\`${lang}\n${body}\n\`\`\``]
      }

      return [b]
    })
    return wrapped.join('\n\n')
  }

  return segments
    .map((seg) => (seg.startsWith('```') ? seg : wrapBlocksInSegment(seg)))
    .join('')
}

    let working = markdown

    // 將仍然像程式碼的段落或長行包成 fenced code，避免後續被當作純文字
    if (!isStructuredNote) {
      working = wrapCodeLikeBlocks(working)
    }
    
    working = convertBareAligned(working)
    working = convertLooseAligned(working)
    working = convertMathFences(working)
    working = convertInlineDelimiters(working)
    working = wrapLatexInListItems(working)
    working = wrapBareLatexDisplayLines(working)
    working = wrapBareLatexLines(working)
    working = renderMathExpressions(working)
      .replace(/^#+\s*(download|reprocess[\d]+).*$/gim, '')
      .replace(/\n.*download.*\n/gim, '\n')
      .replace(/\n.*reprocess.*\n/gim, '\n')
      // Remove hallucinated math wrapper divs that leak into markdown
      .replace(/<div class="math-text-block"[^>]*>/gi, '')
      .replace(/<\/div>/gi, '')

    const contentLines = working
      .split('\n')
      .filter((line) => line.trim().length > 10)

    if (!isStructuredNote) {
      // 移除重複的標題和元數據
      working = working
        .replace(/^#+\s*學習主題\s*$/gm, '')
        .replace(/^#+\s*程式設計概念.*$/gm, '')
        .replace(/^#+\s*自動生成ノート.*$/gm, '')
        .replace(/^#+\s*自動生成ノート\s*\/\s*Auto-Generated Note\s*$/gm, '')
        .replace(/^-?\s*生成時間:.*$/gm, '')
        .replace(/^-?\s*顯示語系:.*$/gm, '')
        .replace(/^-?\s*處理的場景數:.*$/gm, '')
        .replace(/^-?\s*✅\s*包含日文原文.*$/gm, '')
        .replace(/^-?\s*Prompt profile:.*$/gm, '')
        // 移除重複的章節標題
        .replace(/^#+\s*第[0-9]+章.*$/gm, '')
        .replace(/^#+\s*[0-9]+\.[0-9]+\s*.*$/gm, '')
        .replace(/^#+\s*[0-9]+\.[0-9]+\.[0-9]+\s*.*$/gm, '')
        // 移除無用的術語表（如果包含個人資訊）
        .replace(/^\|.*24ca0244.*\|.*$/gm, '')
        .replace(/^\|.*林家誠.*\|.*$/gm, '')
        .replace(/^\|.*學號.*\|.*$/gm, '')
        .replace(/^\|.*姓名.*\|.*$/gm, '')
        .replace(/\n\s*\n\s*\n/g, '\n\n') // 清理多餘空行

      if (!working.includes('學習主題') && !working.includes('主題')) {
        working = `# ${generateTopicFromContent(contentLines)}\n\n${working}`
      }
    }

    const renderer = new marked.Renderer()

    renderer.heading = (text, level, raw) => {
      const clean = (raw || text || '')
        .replace(/\{\{#?[^}]+\}\}/g, '')
        .replace(/\{\{\/[^\{]+\}\}/g, '')
        .replace(/\s+/g, ' ')
        .trim()

      const title = clean
        .replace(/^#+\s+/, '')
        .replace(/```\w+\s*$/i, '')
        .trim()
        
      // 輔助函數：生成帶圖示的標題 HTML
      const makeHeading = (tag, body, icon = '', extraClass = '') => {
        const id = `heading-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
        // 不再包裹 section，只返回標題本身，由後處理進行分組
        return `<${tag} id="${id}" class="note-heading note-heading--${extraClass || 'default'}">
          ${icon ? `<span class="heading-icon">${icon}</span>` : ''}
          <span class="heading-text">${body}</span>
        </${tag}>`
      }

      if (level === 1) {
        const learningTopicLabel = translate('learningTopic') || '學習主題'
        return makeHeading('h1', title, '🎯', 'primary')
      }

      if (level === 2) {
        if (/講義圖片|📸|📖|圖片說明|圖片.*:|image/i.test(title)) {
          return makeHeading('h2', title, '📸', 'image')
        }
        if (/📌|📘|💻|🔧|日文重點|中文說明|中文詳解|程式碼|補充/i.test(title)) {
          return makeHeading('h2', title, '💡', 'explain')
        }
        return makeHeading('h2', title, '', 'secondary')
      }

      if (level === 3) {
        return makeHeading('h3', title)
      }

      // Default for other levels
      return `<h${level} class="note-heading">${title}</h${level}>`
    }

    renderer.code = (code, language) => {
      const codeId = nextCodeId()
      const rawText = maybeExtractTextFromHighlightedHtml(code)
      let lang = (language || '').toString().trim() || ''
      if (!lang || /^plain(text)?$/i.test(lang) || /^text$/i.test(lang)) {
        lang = guessCodeLanguage(rawText)
      }
      if (!lang) lang = 'text'
      const copyLabel = translate('copy') || '複製'
      // 使用 highlight.js：保留高亮（並交由 DOMPurify 清理）
      let highlighted = ''
      try {
        if (lang && hljs.getLanguage(lang)) {
          highlighted = hljs.highlight(rawText, { language: lang }).value
        } else {
          highlighted = hljs.highlightAuto(rawText).value
        }
      } catch (_e) {
        highlighted = escapeHtml(rawText)
      }
      return `<div class="code-container" data-no-enhance="true">
  <div class="code-header">
    <span class="code-language">${escapeHtml(lang)}</span>
    <button class="code-copy-btn" type="button" data-code-id="${codeId}">${escapeHtml(copyLabel)}</button>
  </div>
  <pre class="code-block plain-code-block" data-no-enhance="true">
    <code id="${codeId}" class="plain-code hljs language-${escapeHtml(lang)}">${highlighted}</code>
  </pre>
</div>`
    }

    renderer.paragraph = (text) => {
      if (!text) return ''
      const clean = text.replace(/\{\{#?[^}]+\}\}/g, '').replace(/\{\{\/[^{]+\}\}/g, '')
      if (!hasMeaningfulText(clean)) return ''
      // Ensure inline markdown is parsed if marked didn't do it (though marked usually does)
      // But if text contains raw markdown like **foo**, it means marked didn't parse it.
      // This can happen if the paragraph is inside another block that prevents parsing.
      // However, we can try to parse inline markdown manually if needed, but marked.parseInline is better.
      // Since we are inside a renderer, calling marked.parse might be recursive or wrong context.
      // But let's trust marked passed us parsed HTML for inline elements.
      // If the user sees **foo**, it means marked treated it as text.
      // We can try to force a re-parse of inline elements if we detect them.
      let content = clean
      if (content.includes('**') || content.includes('*') || content.includes('`')) {
         try {
           content = marked.parseInline(content)
         } catch (e) {
           // ignore
         }
      }
      return `<p style="margin: 16px 0; line-height: 1.6; color: var(--text);">${content}</p>`
    }

    renderer.list = (body, ordered) => {
      const tag = ordered ? 'ol' : 'ul'
      const style = ordered
        ? 'margin: 16px 0; padding-left: 24px; color: var(--text);'
        : 'margin: 16px 0; padding-left: 24px; color: var(--text);'
      return `<${tag} style="${style}">${body}</${tag}>`
    }

    renderer.listitem = (text) => {
      const clean = text.replace(/\{\{#?[^}]+\}\}/g, '').replace(/\{\{\/[^{]+\}\}/g, '')
      if (!hasMeaningfulText(clean)) return ''
      let content = clean
      if (content.includes('**') || content.includes('*') || content.includes('`')) {
         try {
           content = marked.parseInline(content)
         } catch (e) {
           // ignore
         }
      }
      return `<li style="margin: 8px 0; line-height: 1.5;">${content}</li>`
    }

    const formatCodeText = (txt = '') => {
      if (!txt || txt.length < 40) return txt
      let t = txt
      // 常見的「整段壓成一行」：註解後直接接程式碼
      t = t.replace(/(\/\/[^\n]*?)\s+(?=(public|private|protected|class|interface|enum|static|final|void|int|double|float|boolean|String)\b)/g, '$1\n')
      t = t.replace(/;\s*/g, ';\n')
      t = t.replace(/\{\s*/g, '{\n')
      t = t.replace(/\}\s*/g, '\n}\n')
      t = t.replace(/\n{3,}/g, '\n\n')
      return t
    }

    const isTextLikeBlock = (txt = '') => {
      const lines = (txt || '').split('\n').filter(l => l.trim().length)
      if (!lines.length) return false
      const codeish = lines.filter(l => /[;{}]|public\s+class|function\s+|def\s+|class\s+|#include|System\.out|console\.log/.test(l)).length
      return (codeish / lines.length) < 0.3
    }

    const looksCodeish = (txt = '') => {
      const lines = (txt || '').split('\n')
      const symbolCount = (txt.match(/[;{}()[\]=<>]/g) || []).length
      const keywordHit = /(class\s+\w+|public\s+|private\s+|protected\s+|def\s+\w+|function\s+\w+|#include|import\s+\w+|package\s+\w+|console\.log|System\.out|return\s+|extends\s+\w+)/i.test(txt)
      const commentHit = lines.some(l => /^\s*(\/\/|#|\/\*|\*)/.test(l))
      const assignHit = /=/.test(txt) && lines.length >= 2
      const minSymbols = Math.max(2, lines.length) // 2 symbols for short blocks, else proportional
      return keywordHit || commentHit || assignHit || symbolCount >= minSymbols
    }

    const shouldBePlainText = (lang, cjkCount, asciiCount, texty, codeish) => {
      if (codeish) return false
      if (texty) return true
      const langLower = String(lang || '').toLowerCase()
      const keepLangFence = new Set([
        'java', 'python', 'cpp', 'c', 'c++', 'javascript', 'typescript', 'bash', 'shell',
        'json', 'yaml', 'yml', 'xml', 'html', 'css', 'sql', 'go', 'rust', 'php', 'ruby',
        'csharp', 'cs', 'kotlin', 'swift'
      ])
      if (langLower && keepLangFence.has(langLower) && langLower !== 'text' && langLower !== 'plaintext') return false
      if (!lang || lang === 'text') return true
      if (cjkCount >= 50 && cjkCount > asciiCount * 0.5) return true
      return false
    }

    renderer.code = (code, language) => {
      code = maybeExtractTextFromHighlightedHtml(code)
      let lang = (language || 'text').replace(/\s*\/\/.*$/, '').replace(/^text\/\//, 'text').trim()
      diagnostics.codeBlocks++
      diagnostics.injectedButtons++
      const decodedMathHtml = maybeDecodeEscapedMathHtml(code)
      if (decodedMathHtml) return decodedMathHtml
      // Tighten math detection: only if explicit language or delimiters
      const mathLike = (lang === 'math' || lang === 'latex' || lang === 'tex') || 
                       /^\$\$[\s\S]+\$\$$/.test(code.trim()) || 
                       /^\\[[\s\S]+\\]$/.test(code.trim())
      const codeish = looksCodeish(code)

      // 若語言未知但內容像程式碼，先嘗試推斷語言；推不出再回退到 plaintext
      if (!lang || lang === 'text' || lang === 'plaintext') {
        const inferred = guessCodeLanguage(code)
        lang = inferred && inferred !== 'text' ? inferred : (codeish ? 'plaintext' : 'text')
      }
      if (mathLike) {
        const fixed = normalizeMathSymbols(normalizeLatexBackslashes(code))
        const wrapped = fixed.includes('$') ? fixed : `$$\n${fixed}\n$$`
        const rendered = renderMathExpressions(wrapped)
        return `<div class="math-text-block" data-no-enhance="true">${rendered}</div>`
      }

      // 特殊錯誤：把「公式 + 程式碼」壓成同一個 code fence（且同一行）
      // 嘗試拆出前段公式，避免把公式塞進 code container
      const splitNarrativePrefix = (text) => {
        const source = String(text || '')
        if (!source.trim()) return null
        const patterns = [
          /\bpublic\s+class\b/i,
          /\bclass\s+\w+\b/i,
          /\bimport\s+\w+/i,
          /\bpackage\s+\w+/i,
          /\bdef\s+\w+\s*\(/i,
          /\bfunction\s+\w+\s*\(/i,
          /#include\b/i,
          /\bSystem\.out\b/i,
          /\bconsole\.log\b/i
        ]
        let idx = -1
        for (const re of patterns) {
          const found = source.search(re)
          if (found >= 0 && (idx === -1 || found < idx)) idx = found
        }
        if (idx <= 0) return null
        const prefix = source.slice(0, idx).trim()
        const tail = source.slice(idx).trim()
        if (prefix.length < 20 || !tail) return null
        const cjk = (prefix.match(/[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9fff]/g) || []).length
        const sym = (prefix.match(/[;{}()[\]=<>]/g) || []).length
        const cjkRatio = cjk / Math.max(1, prefix.length)
        const symRatio = sym / Math.max(1, prefix.length)
        const tailLooksCodeish =
          /(class\s+\w+|public\s+|private\s+|protected\s+|def\s+\w+|function\s+\w+|#include|import\s+[\w.]+|System\.out|console\.log|return\s+)/i.test(tail) ||
          (tail.match(/[;{}()[\]=<>]/g) || []).length >= 6
        if (!tailLooksCodeish) return null
        if (cjkRatio < 0.45 || symRatio > 0.1) return null
        return { prefix, tail }
      }

      let leadingMathHtml = ''
      let leadingTextHtml = ''
      if (!code.includes('\n')) {
        const startRe = /(?:\b(java|python|javascript|typescript|cpp|c\+\+|c#|csharp|sql)\b\s+)?(?=(public\s+|private\s+|protected\s+|class\s+\w+|import\s+|package\s+|def\s+|function\s+))/i
        const m = startRe.exec(code)
        if (m && m.index > 0) {
          const prefix = code.slice(0, m.index).trim()
          const tail = code.slice(m.index).trim()
          const prefixMath = /(\bpi\b|π|∑|Σ|\\sum|\\pi|\\frac|\\int)/.test(prefix) && (prefix.match(/[=+*_^(){}[\]|]/g) || []).length >= 2
          if (prefixMath) {
            const fixed = normalizeLatexBackslashes(prefix)
            const wrapped = fixed.includes('$') ? fixed : `$$${fixed}$$`
            leadingMathHtml = `<div class="math-text-block" data-no-enhance="true">${renderMathExpressions(wrapped)}</div>`
            code = tail
          }
        }
      }
      let cleanCode = code
        .replace(/(^|\n)[\t ]*text[\t \u200B]*(\/\/)/gi, '$1$2')
        .replace(/(^|\n)[\t ]*text[\t \u200B]+(?=import|from|def|class|public|void|int|enum|struct|interface)/gi, '$1')
        .replace(/(^|\n)[\t ]*text[\t \u200B]*(?=[{\[(<\\-])/gi, '$1')
        .replace(/(^|\n)[\t ]*text[\t \u200B]+(?=\d+:)/gi, '$1')
        .replace(/(^|\n)[\t ]*text[\t \u200B]+(?=\/\/|\/\*|import|from|def|class|public|private|protected|void|int|double|float|boolean|String)/gi, '$1')
        .replace(/\btext\b\s*(?=\/\/)/gi, '')
        .replace(/^```\w*\s*/, '').replace(/\s*```$/, '')
        // Strip HTML tags that might be hallucinated inside the code block (including malformed <spanclass=...>)
        .replace(/<\/?(spanclass|span|div|p|code|pre|br|strong|em|b|i|mark)[^>]*>/gi, '')
        // Strip escaped tags that sometimes leak into fenced code
        .replace(/&lt;\/?(spanclass|span)[^&]*?&gt;/gi, '')
        .replace(/\bspanclass\s*=\s*["'][^"']*["']>?/gi, '')
        .replace(/\bhljs\b/gi, '')
        .replace(/\bh?l?js-[a-z0-9_-]+\b/gi, '')

      cleanCode = formatCodeText(cleanCode)
      // 移除連續重複行（常見於 OCR/LLM 的重複）
      cleanCode = (() => {
        const lines = cleanCode.split('\n')
        const out = []
        let prev = null
        for (const line of lines) {
          const trimmed = line.trim()
          if (prev === line && trimmed.length >= 16) continue
          out.push(line)
          prev = line
        }
        return out.join('\n')
      })()
      // 常見 LLM 失誤：把語言標籤當成正文的一行（例如 "java"）
      cleanCode = cleanCode.replace(/(^|\n)\s*(java|python|javascript|typescript|cpp|c\+\+|c#|csharp|sql|bash|shell|plaintext)\s*(?=\n)/gi, '$1')
      cleanCode = cleanCode.replace(/(^|\n)\s*(java|python|javascript|typescript|cpp|c\+\+|c#|csharp|sql|bash|shell)\s*(?=\/\/|\/\*|#)/gi, '$1')
      cleanCode = cleanCode.replace(/(^|\n)\s*(java|python|javascript|typescript|cpp|c\+\+|c#|csharp|sql|bash|shell)\s+(?=(public|private|protected|class|interface|enum|static|final|void|int|double|float|boolean|String|import|package)\b)/gi, '$1')
      cleanCode = cleanCode.replace(/\b(java|python|javascript|typescript|cpp|c\+\+|c#|csharp|sql|bash|shell)\b\s*\/\/\s*\1\b/gi, '//')
      cleanCode = cleanCode.replace(/\}\s*(java|python|javascript|typescript|cpp|c\+\+|c#|csharp|sql|bash|shell)\b/gi, '}')
      // 常見跳針：class class class...
      cleanCode = cleanCode
        .replace(/\b(class)(\s+\1){3,}\b/gi, '$1')
        .replace(/\b(public)(\s+\1){3,}\b/gi, '$1')
        .replace(/\b(private)(\s+\1){3,}\b/gi, '$1')
        .replace(/\b(protected)(\s+\1){3,}\b/gi, '$1')

      const escapeHtml = (s = '') => s
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')

      const narrativeSplit = splitNarrativePrefix(cleanCode)
      if (narrativeSplit) {
        leadingTextHtml = `<p class="plain-text-block">${escapeHtml(narrativeSplit.prefix).replace(/\n/g, '<br>')}</p>`
        cleanCode = narrativeSplit.tail
      }

      const cjkCount = (cleanCode.match(/[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9fff]/g) || []).length
      const asciiCount = (cleanCode.match(/[A-Za-z0-9_;{}()[\]=+\-*/<>$\\]/g) || []).length
      const texty = isTextLikeBlock(cleanCode)
      const codeishBlock = codeish || looksCodeish(cleanCode)

      if (shouldBePlainText(lang, cjkCount, asciiCount, texty, codeishBlock)) {
        return `<p class="plain-text-block">${escapeHtml(cleanCode).replace(/\n/g, '<br>')}</p>`
      }

      if (!cleanCode.trim()) return ''

      const codeId = nextCodeId()
      const copyLabel = translate('copy') || '複製'
      let highlighted = ''
      const inferred = (!lang || /^plain(text)?$/i.test(lang) || /^text$/i.test(lang) || /^plaintext$/i.test(lang))
        ? guessCodeLanguage(cleanCode)
        : ''
      if (inferred) lang = inferred
      try {
        if (lang && hljs.getLanguage(lang)) {
          highlighted = hljs.highlight(cleanCode, { language: lang }).value
        } else {
          highlighted = hljs.highlightAuto(cleanCode).value
        }
        if (!/<span\b/i.test(highlighted)) {
          const fallbackLang = guessCodeLanguage(cleanCode)
          if (fallbackLang && hljs.getLanguage(fallbackLang)) {
            highlighted = hljs.highlight(cleanCode, { language: fallbackLang }).value
            lang = fallbackLang
          }
        }
      } catch (_e) {
        highlighted = escapeHtml(cleanCode)
      }
      return `${leadingMathHtml}${leadingTextHtml}<div class="code-container" data-no-enhance="true">
  <div class="code-header">
    <span class="code-language">${escapeHtml(lang || 'text')}</span>
    <button class="code-copy-btn" type="button" data-code-id="${codeId}">${escapeHtml(copyLabel)}</button>
  </div>
  <pre class="code-block plain-code-block" data-no-enhance="true">
    <code id="${codeId}" class="hljs language-${escapeHtml(lang || 'text')}">${highlighted}</code>
  </pre>
</div>`
    }

    renderer.blockquote = (quote) => {
      const clean = quote.replace(/\{\{#?[^}]+\}\}/g, '').replace(/\{\{\/[^{]+\}\}/g, '')
      if (!hasMeaningfulText(clean)) return ''
      return `<blockquote style="margin: 16px 0; padding: 16px; border-left: 4px solid var(--accent); background: var(--surface); color: var(--text); font-style: italic;">${clean}</blockquote>`
    }

    renderer.table = (header, body) => {
      return `<div class="table-wrapper" style="width: 100%; overflow-x: auto; margin: 16px 0;"><table class="enhanced-table" style="width: 100%; min-width: 100%; border-collapse: collapse; color: var(--text);">
        <thead>${header}</thead>
        <tbody>${body}</tbody>
      </table></div>`
    }

    renderer.tablerow = (content) => {
      return `<tr style="border-bottom: 1px solid var(--border);">${content}</tr>`
    }

    renderer.tablecell = (content, flags) => {
      const tag = flags.header ? 'th' : 'td'
      const style = flags.header
        ? 'padding: 12px; font-weight: 600; background: var(--surface); border-bottom: 2px solid var(--accent); white-space: nowrap;'
        : 'padding: 12px; border-bottom: 1px solid var(--border); word-wrap: break-word; word-break: break-word;'
      return `<${tag} style="${style}">${content}</${tag}>`
    }

    const replaceImagesOutsideFences = (md = '') => {
      return md
        .split(CODE_FENCE_SPLIT_REGEX)
        .map((seg) => {
          if (seg.startsWith('```')) return seg
          return seg.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_match, alt, src) => {
            const correctedSrc = normalizeImageHref(src)
            return `\n\n<img src="${correctedSrc}" alt="${alt || '課程截圖'}" style="max-width: min(800px, 100%); height: auto; display: block; margin: 16px auto; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);" />\n\n`
          })
        })
        .join('')
    }

    let preprocessed = replaceImagesOutsideFences(working)
      // 移除空的 text fenced block（避免產生空白代碼框）
      .replace(/```(?:text)?\s*\n\s*\n```/g, '')
      // 移除任何語言的空 fenced block
      .replace(/```[A-Za-z0-9+#.-]*\s*\n\s*```/g, '')
      // 移除殘留的 math-inline span 文字包裹 (DISABLED: This breaks valid KaTeX output)
      // .replace(/<span class="math-inline">([\s\S]*?)<\/span>/gi, '$1')
      // .replace(/<span class="katex">([\s\S]*?)<\/span>/gi, '$1')
      // .replace(/<span class="katex-mathml">[\s\S]*?<\/span>/gi, '')
      // 檢測單行 math/latex 模式（無 fenced）
      .replace(/^\s*math\s+(\\begin\{aligned\}[\s\S]*?\\end\{aligned\})/gim, (_m, body) => {
        const rendered = renderMathExpressions(`$$${body}$$`)
        return `<div class="math-text-block" data-no-enhance="true">${rendered}</div>`
      })

    // 將孤立的 <pre><code> 包裝成 ChatGPT 風格容器（避免後端直接輸出 HTML 沒有複製鈕）
    let html = marked.parse(preprocessed, { 
      renderer,
      mangle: false,
      headerIds: false
    })
    const cleaned = cleanHtmlEntities(html)
    const sanitizerConfig = {
      ADD_TAGS: [
        'div',
        'span',
        'pre',
        'code',
        'blockquote',
        'img',
        'mark',
        'details',
        'summary',
        'table',
        'thead',
        'tbody',
        'th',
        'td',
        'button',
        'math',
        'mrow',
        'mi',
        'mo',
        'mn',
        'msup',
        'msub',
        'mfrac',
        'msqrt',
        'mstyle',
        'mspace',
        'mtable',
        'mtr',
        'mtd',
        'msubsup',
        'semantics',
        'annotation',
      ],
      ADD_ATTR: [
        'class',
        'id',
        'type',
        'src',
        'alt',
        'title',
        'loading',
        'style',
        'href',
        'z-index',
        'data-code-id',
        'aria-hidden',
        'role',
        'focusable',
      ],
      KEEP_CONTENT: true,
    }
    const sanitized = sanitizeHtml(cleaned, sanitizerConfig)

    const endedAt = performance?.now ? performance.now() : Date.now()
    diagnostics.renderMs = Math.round(endedAt - startedAt)

    // 全局移除 inline style，避免舊版行內樣式鎖定排版
    const stripInlineStyle = (html) => html.replace(/ style="[^"]*"/gi, '')
    // 同時移除內嵌寬高屬性，避免圖片撐爆版面
    const stripDimensions = (html) => html.replace(/\s(width|height)="[^"]*"/gi, '')

    // 圖片清理：移除寬高與 style，強制附加 mk-img 以便統一縮放
    const clampImages = (html) => {
      return html.replace(/<img([^>]*?)>/gi, (_m, attrs = '') => {
        let cleaned = attrs
          .replace(/\s(width|height)="[^"]*"/gi, '')
          .replace(/\sstyle="[^"]*"/gi, '')
        if (!/class="/i.test(cleaned)) {
          cleaned += ' class="mk-img"'
        } else {
          cleaned = cleaned.replace(/class="/i, 'class="mk-img ')
        }
        return `<img ${cleaned}>`
      })
    }

    // 移除殘留的 highlight.js 樣式跨度（可能被當成純文字顯示）
    const normalizeOutput = (inputHtml) => {
      const stripped = clampImages(stripDimensions(stripInlineStyle(inputHtml)))
      return stripSpanArtifacts(stripResidualHighlightSpans(
        normalizeLegacyCodeBlocks(stripped, { createCodeId: nextCodeId })
      ))
    }
    const normalizedHtml = normalizeOutput(sanitized)
    const decodedHtml = decodeEscapedMathHtmlBlocks(normalizedHtml)
    const finalHtml = decodedHtml !== normalizedHtml
      ? normalizeOutput(sanitizeHtml(decodedHtml, sanitizerConfig))
      : normalizedHtml
    const enhancedHtml = enhanceJapaneseSections(finalHtml)

    return {
      html: enhancedHtml,
      diagnostics,
    }
  } catch (error) {
    diagnostics.warnings.push(`Render error: ${error.message}`)
    return {
      html: `<div style="color: var(--warn); padding: 16px; border: 1px solid var(--warn); border-radius: 4px;">渲染錯誤: ${error.message}</div>`,
      diagnostics,
    }
  }
}

const normalizeImageHref = (href) => {
  if (!href) return ''
  if (href.startsWith('http')) return href
  if (href.startsWith('/')) return href
  return `/${href}`
}

export const buildMarkdownFromStructured = (structured, fallbackTitle) => {
  const note = Array.isArray(structured) ? { sections: structured } : (structured || {})
  const parts = []
  const meta = note.meta || {}
  const title = meta.title || note.title || note.courseName || fallbackTitle || 'Note'
  
  // 不添加重複的標題
  if (!note.title && !meta.title) {
    parts.push(`# ${title}`)
  }
  
  const metaLines = []
  if (meta.analyzed_at) metaLines.push(`- Date: ${new Date(meta.analyzed_at).toLocaleString()}`)
  if (note.date) metaLines.push(`- Date: ${note.date}`)
  if (meta.lang) metaLines.push(`- Lang: ${meta.lang}`)
  if (Array.isArray(meta.source)) metaLines.push(`- Sources: ${meta.source.length}`)
  if (metaLines.length) parts.push(metaLines.join('\n'))

  // 檢測低品質數據
  const hasEmptyStructure = (
    (Array.isArray(note.notes) && note.notes.length === 0) ||
    (Array.isArray(note.terms) && note.terms.length === 0) ||
    (Array.isArray(note.summary) && note.summary.length === 0)
  )
  
  const hasQualityIssue = note.quality === 'poor' || note.quality === 'fair'
  
  if (hasQualityIssue || hasEmptyStructure) {
    parts.push(`## ⚠️ 處理品質問題`)
    if (note.message) {
      parts.push(note.message)
    } else {
      parts.push('資料品質有限，建議上傳更清晰的講義。')
    }
    parts.push('')
  }

  // 處理場景數據（多章節）
  if (note.scene_summaries && Array.isArray(note.scene_summaries)) {
    note.scene_summaries.forEach((scene, index) => {
      parts.push(`# 章節 ${index + 1}`)
      
      // 添加圖片
      if (scene.image_path_final) {
        parts.push(`![課程截圖](${scene.image_path_final})`)
        parts.push('')
      }
      
      // 添加日文重點
      if (scene.ocr_text) {
        const jpLines = scene.ocr_text.split('\n').filter(line => 
          line.trim() && 
          !line.includes('宇山亮') && 
          !line.includes('24ca0244') &&
          !line.includes('林家誠')
        ).slice(0, 3)
        
        if (jpLines.length > 0) {
          parts.push(createNoteHeading('primary', '② 日文重點大綱（原講義語言）'))
          parts.push('')
          jpLines.forEach((line, i) => {
            parts.push(`${i + 1}. ${line.trim()}`)
          })
          parts.push('')
        }
      }
      
      // 添加場景摘要
      if (scene.summary) {
        parts.push(createNoteHeading('explain', '③ 母語解析（中文）'))
        parts.push('')
        parts.push(scene.summary)
        parts.push('')
      }
      
      parts.push('---')
      parts.push('')
    })
  }

  // 處理一般筆記內容
  if (note.notes && Array.isArray(note.notes)) {
    note.notes.forEach(noteItem => {
      if (noteItem.original) {
        parts.push(createNoteHeading('primary', '📝 日文原文重點'))
        parts.push('')
        parts.push(noteItem.original)
        parts.push('')
      }
      if (noteItem.explanation) {
        const secondaryLabel = note.secondary_label || '重點說明'
        parts.push(createNoteHeading('explain', `📖 ${secondaryLabel}`))
        parts.push('')
        parts.push(noteItem.explanation)
        parts.push('')
      }
      if (noteItem.supplements && Array.isArray(noteItem.supplements)) {
        parts.push(createNoteHeading('supplement', '⑥ 補充說明 / 延伸理解'))
        parts.push('')
        noteItem.supplements.forEach(supplement => {
          parts.push(`- ${supplement}`)
        })
        parts.push('')
      }
    })
  }

  // ④ 術語表
  if (note.terms && Array.isArray(note.terms)) {
    const filteredTerms = note.terms.filter(term =>
      !term.jp?.includes('24ca0244') &&
      !term.jp?.includes('林家誠') &&
      !term.secondary?.includes('24ca0244') &&
      !term.secondary?.includes('林家誠')
    )

    if (filteredTerms.length > 0) {
      const secondaryLabel = note.secondary_label || '翻譯'
      parts.push(createNoteHeading('glossary', '④ 術語表'))
      parts.push('')
      filteredTerms.forEach(term => {
        parts.push(`- **${term.jp || ''}** | ${term.secondary || ''} (${secondaryLabel})`)
      })
      parts.push('')
    }
  }

  // ⑤ 程式碼 / 數學公式（若有）
  if (note.code && note.code.code) {
    parts.push(createNoteHeading('code', '⑤ 程式碼 / 數學公式（若有）'))
    parts.push(`\`\`\`${note.code.lang || 'text'}`)
    parts.push(note.code.code)
    parts.push(`\`\`\``)
    parts.push('- 🔍 逐行說明：請總結程式流程與輸出重點')
    parts.push('')
  }

  // 問答/練習題：影像筆記不再注入

  return parts.join('\n')
}
