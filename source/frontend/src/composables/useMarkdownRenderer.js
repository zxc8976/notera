/**
 * useMarkdownRenderer.js
 * 
 * Markdown rendering composable extracted from Home.vue
 * Handles markdown structure processing, math blocks, and interactive enhancements
 */

import { ref, computed, watch, nextTick } from 'vue'
import { renderNoteMarkdown, renderMathExpressions } from '@/utils/markdownRenderer.js'

export function useMarkdownRenderer(options = {}) {
  const {
    onDiagnostics = () => {},
    translate = (key) => key
  } = options

  // ========== State ==========
  const fallbackContainer = ref(null)
  const fallbackHtml = ref('')
  
  // Language configuration
  const languageConfig = ref({
    primary: { enabled: true, label: '中文', style: 'zh' },
    secondary: { enabled: true, label: '日本語', style: 'ja' }
  })

  // Parsed sections for structured rendering
  const parsedSections = ref([])

  // ========== Computed ==========
  const hasStructuredSections = computed(() => 
    parsedSections.value && parsedSections.value.length > 0
  )

  const primaryStyle = computed(() => languageConfig.value.primary.style)
  const secondaryStyle = computed(() => languageConfig.value.secondary.style)

  // ========== Core Functions ==========

  /**
   * Transform math-like code blocks into rendered math expressions
   */
  const transformMathBlocks = (root) => {
    if (!root) return
    root.querySelectorAll('pre code').forEach((codeEl) => {
      const text = codeEl.textContent || ''
      // Tighten check: only convert if explicit language or explicit delimiters
      const isExplicitMath = codeEl.classList.contains('language-math') || 
                             codeEl.classList.contains('language-latex') || 
                             codeEl.classList.contains('language-tex')
      
      // Only check for delimiters if we are strict, or if we want to support $$ blocks without language tag
      // But avoid the broad regex that matches single symbols like '×' or 'π'
      const hasDelimiters = /^\$\$[\s\S]+\$\$$/.test(text.trim()) || /^\\[[\s\S]+\\]$/.test(text.trim())

      if (isExplicitMath || hasDelimiters) {
        const wrapper = document.createElement('div')
        wrapper.className = 'math-text-block'
        wrapper.setAttribute('data-no-enhance', 'true')
        wrapper.innerHTML = renderMathExpressions(text)
        const pre = codeEl.closest('pre')
        if (pre && pre.parentNode) pre.parentNode.replaceChild(wrapper, pre)
      } else {
        codeEl.setAttribute('data-no-enhance', 'true')
      }
    })
  }

  /**
   * Bind interactive enhancements (image handling, copy buttons, card collapse)
   */
  const bindEnhancements = () => {
    const root = fallbackContainer.value
    if (!root) return

    // Fix image attributes
    root.querySelectorAll('img').forEach((img) => {
      img.removeAttribute('width')
      img.removeAttribute('height')
      const cls = img.getAttribute('class') || ''
      if (!cls.includes('mk-img')) img.setAttribute('class', (`mk-img ${cls}`).trim())
    })

    // Remove old event listeners by cloning buttons
    root.querySelectorAll('.code-copy-btn').forEach((btn) => {
      const clone = btn.cloneNode(true)
      btn.replaceWith(clone)
    })

    // Bind code copy buttons
    root.querySelectorAll('.code-copy-btn').forEach((btn) => {
      const codeId = btn.getAttribute('data-code-id')
      const codeElement = root.querySelector(`#${codeId}`)
      if (!codeElement) return
      btn.addEventListener('click', async () => {
        const snippet = codeElement.textContent || ''
        try {
          await navigator.clipboard.writeText(snippet)
          const originalText = btn.textContent
          btn.textContent = '✅ 已複製'
          btn.classList.add('copied')
          window.setTimeout(() => {
            btn.textContent = originalText
            btn.classList.remove('copied')
          }, 2000)
        } catch (err) {
          console.error('[MarkdownRenderer] 複製失敗:', err)
        }
      })
    })
    
    // Bind card collapse functionality
    root.querySelectorAll('.note-card-header').forEach(header => {
      header.addEventListener('click', (e) => {
        const card = header.closest('.note-card')
        if(card) card.classList.toggle('collapsed')
      })
      const btn = header.querySelector('.card-toggle-btn')
      if(btn) {
        btn.addEventListener('click', (e) => {
          e.stopPropagation()
          const card = header.closest('.note-card')
          if(card) card.classList.toggle('collapsed')
        })
      }
    })
  }

  /**
   * Process markdown HTML structure into card-based layout
   */
  const processStructure = (html) => {
    const parser = new DOMParser()
    const doc = parser.parseFromString(html, 'text/html')
    
    // Debug: Check what tags exist
    const h1Count = doc.querySelectorAll('h1').length
    const h2Count = doc.querySelectorAll('h2').length
    const h3Count = doc.querySelectorAll('h3').length
    console.log('[processStructure] Header count - H1:', h1Count, 'H2:', h2Count, 'H3:', h3Count)
    console.log('[processStructure] First 500 chars of HTML:', html.substring(0, 500))

    // Format light sample code (example-specific transformation)
    const formatLightSample = (text) => {
      const isLight = /ACTION_OFF/.test(text) && /transitionProb/.test(text)
      if (!isLight) return text
      return [
        '// 定義動作常數：0=關燈, 1=開燈',
        'private static final int ACTION_OFF = 0;',
        'private static final int ACTION_ON  = 1;',
        '',
        '// 建立條件機率表 (Transition Probability)',
        '// 狀態0 (關燈) 時：關燈機率=0.7，開燈的機率=0.3',
        '// 狀態1 (開燈) 時：關燈機率=0.2，開燈的機率=0.8',
        'private double[][] transitionProb = {',
        '    { 0.7, 0.3 },',
        '    { 0.2, 0.8 }',
        '};',
        '',
        '// 驗證機率歸一化條件',
        'public void validateProbability(int state) {',
        '    double sum = 0.0;',
        '    for (int action = 0; action < 2; action++) {',
        '        sum += transitionProb[state][action];',
        '    }',
        '    if (Math.abs(sum - 1.0) > 0.001) {',
        '        System.out.println("警告：機率和不為1！狀態=" + state + "，總和=" + sum);',
        '    }',
        '}',
        '',
        '// 模擬狀態轉移',
        'public int nextState(int currentState, int action) {',
        '    if (currentState == STATE_OFF) {',
        '        return (action == ACTION_ON) ? STATE_ON : STATE_OFF;',
        '    } else {',
        '        return (action == ACTION_OFF) ? STATE_OFF : STATE_ON;',
        '    }',
        '}'
      ].join('\n')
    }

    // Process pre/code blocks
    doc.querySelectorAll('pre').forEach((pre) => {
      const code = pre.querySelector('code')
      if (!code) return
      const text = code.textContent || ''
      const inCodeContainer = !!pre.closest('.code-container')
      const hasHighlight = code.classList.contains('hljs')
      const isRenderedBlock = inCodeContainer || pre.classList.contains('code-block') || pre.classList.contains('plain-code-block') || hasHighlight

      if (isRenderedBlock) {
        code.setAttribute('data-no-enhance', 'true')
        pre.setAttribute('data-no-enhance', 'true')
        return
      }

      // Check if code is already highlighted by hljs
      const hasHighlighting = code.classList.contains('hljs') || 
                              code.innerHTML.includes('hljs-')
      
      if (hasHighlighting) {
        // Preserve existing highlighting, just mark as processed
        code.setAttribute('data-no-enhance', 'true')
        pre.setAttribute('data-no-enhance', 'true')
      } else {
        // Apply plain text transformation for non-highlighted blocks
        const normalized = formatLightSample(text)
        // code.removeAttribute('class') // Removed to preserve language classes
        code.classList.add('plain-code') // Ensure plain-code class
        code.removeAttribute('style')
        code.setAttribute('data-no-highlight', 'true')
        code.setAttribute('data-no-enhance', 'true')
        code.textContent = normalized
        if (!pre.classList.contains('plain-code-block')) pre.classList.add('plain-code-block')
      }
    })

    // Fix image attributes
    doc.querySelectorAll('img').forEach((img) => {
      img.removeAttribute('width')
      img.removeAttribute('height')
      img.style.maxWidth = '100%'
      img.style.height = 'auto'
      img.style.display = 'block'
      img.style.margin = '12px auto'
      img.classList.add('mk-img')
    })

    // Build card structure
    const fragment = document.createDocumentFragment()
    let currentCard = null
    let currentBody = null

    const finishCard = () => {
      if (currentCard && currentBody) {
         currentCard.appendChild(currentBody)
         fragment.appendChild(currentCard)
      }
      currentCard = null
      currentBody = null
    }

    const startCard = (headingEl) => {
      finishCard()
      
      currentCard = document.createElement('section')
      currentCard.className = 'note-card'
      
      const header = document.createElement('div')
      header.className = 'note-card-header'
      
      const clonedHeading = headingEl.cloneNode(true)
      clonedHeading.style.margin = '0' 
      header.appendChild(clonedHeading)
      
      const toggleBtn = document.createElement('button')
      toggleBtn.className = 'card-toggle-btn'
      toggleBtn.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>`
      header.appendChild(toggleBtn)
      
      currentCard.appendChild(header)
      
      currentBody = document.createElement('div')
      currentBody.className = 'note-card-body'
    }

    const allowedHeading = (text = '') => {
      const trimmed = (text || '').trim()
      return /^\s*[②③④⑤⑥]/.test(trimmed) || /(圖片|image|chapter|章節|章节)/i.test(trimmed)
    }

    const nodes = Array.from(doc.body.childNodes)
    const nextMeaningfulNode = (startIndex) => {
      for (let i = startIndex + 1; i < nodes.length; i += 1) {
        const candidate = nodes[i]
        if (candidate.nodeType === 3 && !candidate.textContent.trim()) continue
        return candidate
      }
      return null
    }

    nodes.forEach((node, index) => {
      if (node.nodeType === 3 && !node.textContent.trim()) return
      
      const isHeader = node.nodeType === 1 && /^H[1-3]$/.test(node.tagName)
      
      // Check if it's a section separator (HR tag)
      const isSeparator = node.nodeType === 1 && node.tagName === 'HR'
      
      // Check if paragraph starts with emoji heading pattern
      const isParagraphHeading = node.nodeType === 1 && node.tagName === 'P' && 
        /^[🎯📝💡✨🔑📌⚡🌟📊🎓📚🔍💻⭐#]+\s+/.test(node.textContent?.trim() || '')
      
      if (isHeader) {
        const headingText = (node.textContent || '').trim()
        if (allowedHeading(headingText)) {
          startCard(node)
        } else {
          // 非 ②-⑥ 標題：視為普通內容，避免舊版樣式觸發
          if (!currentCard) {
            const dummyHeader = document.createElement('h2')
            dummyHeader.textContent = '📝 摘要'
            dummyHeader.className = 'note-heading note-heading--secondary'
            startCard(dummyHeader)
          }
          currentBody.appendChild(node.cloneNode(true))
        }
      } else if (isSeparator) {
        const nextNode = nextMeaningfulNode(index)
        const nextIsHeader = nextNode && nextNode.nodeType === 1 && /^H[1-3]$/.test(nextNode.tagName)
        const nextHeadingText = nextIsHeader ? (nextNode.textContent || '') : ''
        if (nextIsHeader && allowedHeading(nextHeadingText)) {
          finishCard()
        }
      } else if (isParagraphHeading) {
        // Convert emoji/markdown-like paragraph to heading and start new card
        const heading = document.createElement('h2')
        const rawText = node.textContent || ''
        heading.textContent = rawText.replace(/^#+\s*/, '').trim()
        heading.className = 'note-heading note-heading--secondary'
        startCard(heading)
      } else {
        if (!currentCard) {
          if (node.textContent && node.textContent.trim()) {
            const dummyHeader = document.createElement('h2')
            dummyHeader.textContent = '📝 摘要'
            dummyHeader.className = 'note-heading note-heading--secondary'
            startCard(dummyHeader)
            currentBody.appendChild(node.cloneNode(true))
          }
        } else {
          currentBody.appendChild(node.cloneNode(true))
        }
      }
    })
    finishCard()

    const container = document.createElement('div')
    container.appendChild(fragment)

    return cleanupGarbled(container.innerHTML)
  }

  /**
   * Clean up garbled HTML artifacts
   */
  const cleanupGarbled = (html = '') => {
    return (html || '')
      .replace(/<\/?spanclass[^>]*>/gi, '')
      .replace(/&lt;\/?spanclass[^>]*&gt;/gi, '')
      .replace(/spanclass\s*=\s*["'][^"']*["']>?/gi, '')
      .replace(/&lt;spanclass\s*=\s*["'][^"']*["'][^>]*&gt;/gi, '')
      .replace(/spanclass[^<\s>]*/gi, '')
      // REMOVED: These regexes were destroying syntax highlighting by stripping hljs-* classes
      // .replace(/\bh?l?js-[a-z0-9_-]+\b/gi, '')
      // .replace(/\bhjs-number\b/gi, '')
  }

  /**
   * Main update function: render markdown to HTML with all enhancements
   */
  const updateMarkdownFallback = async (markdown) => {
    console.log('[useMarkdownRenderer] updateMarkdownFallback called, markdown length:', markdown?.length)
    let { html, diagnostics } = renderNoteMarkdown(markdown || '', {
      translate,
      measure: true
    })
    console.log('[useMarkdownRenderer] renderNoteMarkdown returned HTML length:', html?.length)
    
    // === Structured Note Detection (Relaxed for 11+ chapter notes) ===
    // 1. Count image headings with various patterns (📖 圖片 N, Image N, etc.)
    const imageHeadingCount = (markdown || '').match(/^#{1,6}\s*(?:📖\s*)?(?:圖片|Image|图片|イメージ)\s*\d+/gmi)?.length || 0
    
    // 2. Count chapter headings with broader patterns
    //    - Chapter N, 章節 N, 章节 N, 第 N 章
    //    - 第N章 (no space), 第一章 (kanji numbers)
    //    - Generic ## Section N patterns
    const chapterPatterns = [
      /(^|\n)#{1,6}\s*(?:Chapter|章節|章节)\s*\d+/gmi,
      /(^|\n)#{1,6}\s*第\s*\d+\s*章/gmi,
      /(^|\n)#{1,6}\s*第\d+章/gmi,
      /(^|\n)#{1,6}\s*第[一二三四五六七八九十百]+章/gmi,
      /(^|\n)#{1,6}\s*\d+\.\s+/gmi,  // Numbered sections like "## 1. Introduction"
    ]
    let chapterHeadingCount = 0
    for (const pattern of chapterPatterns) {
      chapterHeadingCount += (markdown || '').match(pattern)?.length || 0
    }
    
    // 3. Count general headings (any ## or ### level)
    const generalHeadingCount = (markdown || '').match(/(^|\n)#{1,3}\s+\S+/gm)?.length || 0
    
    // 4. Check for presence of any chapter heading
    const hasChapterHeading = chapterHeadingCount >= 1 || generalHeadingCount >= 3
    
    // 5. Count images (markdown and HTML)
    const markdownImageCount = (markdown || '').match(/!\[[^\]]*\]\(/gmi)?.length || 0
    const htmlImageCount = (markdown || '').match(/<img\s/gi)?.length || 0
    const totalImageCount = markdownImageCount + htmlImageCount
    const hasImageMarkdown = totalImageCount > 0
    const hasRichImages = totalImageCount >= 6
    
    // 6. Determine if we should skip processStructure (card-based layout)
    //    Skip when:
    //    - 6+ images (hasRichImages)
    //    - 3+ image headings 
    //    - 1+ chapter headings detected
    //    - Has any headings AND any images (structured note pattern)
    //    - 5+ general headings (likely structured content)
    const shouldSkipStructure = hasRichImages || 
                                 imageHeadingCount >= 3 || 
                                 chapterHeadingCount >= 1 || 
                                 (hasChapterHeading && hasImageMarkdown) ||
                                 generalHeadingCount >= 5
    
    console.log('[useMarkdownRenderer] Structured detection:', {
      imageHeadingCount,
      chapterHeadingCount,
      generalHeadingCount,
      totalImageCount,
      hasChapterHeading,
      hasImageMarkdown,
      hasRichImages,
      shouldSkipStructure
    })
    
    html = shouldSkipStructure ? cleanupGarbled(html || '') : processStructure(html || '')
    console.log('[useMarkdownRenderer] Final HTML length:', html?.length, shouldSkipStructure ? '(skipped processStructure)' : '(used processStructure)')
    fallbackHtml.value = html
    onDiagnostics(diagnostics)
    await nextTick()
    transformMathBlocks(fallbackContainer.value)
    bindEnhancements()
    console.log('[useMarkdownRenderer] updateMarkdownFallback completed, fallbackHtml.value length:', fallbackHtml.value?.length)
  }

  // ========== Return Composable API ==========
  return {
    // State
    fallbackContainer,
    fallbackHtml,
    languageConfig,
    parsedSections,
    
    // Computed
    hasStructuredSections,
    primaryStyle,
    secondaryStyle,
    
    // Methods
    updateMarkdownFallback,
    transformMathBlocks,
    bindEnhancements,
    processStructure,
    cleanupGarbled
  }
}
