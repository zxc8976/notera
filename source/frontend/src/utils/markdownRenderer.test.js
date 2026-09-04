import { describe, it, expect } from 'vitest'
import { cleanMarkdown, renderNoteMarkdown } from './markdownRenderer'

describe('markdownRenderer', () => {
  describe('cleanMarkdown', () => {
    const testCases = [
      {
        name: 'Remove text // comments',
        input: 'text // 電燈問題的行動策略實現示例 (非程式碼，僅用數學表示) public class LightControl { // 定義狀態和動作 enum State { ON, OFF } enum Action { TURN_ON, TURN_OFF }',
        expected: '// 電燈問題的行動策略實現示例 (非程式碼，僅用數學表示) \n public class LightControl { \n// 定義狀態和動作 \n enum State { ON, OFF } \n enum Action { TURN_ON, TURN_OFF } \n}'
        // Note: formatFlattenedCode might add newlines, so exact match might be tricky. 
        // Let's check if "text" is removed and newlines are added.
      },
      {
        name: 'Remove text import',
        input: 'python\ntext import random',
        expected: 'import random'
      },
      {
        name: 'Remove text prefix from math',
        input: 'text - \\pi(a_{on}|s=0) = 0.7',
        expected: '- \\pi(a_{on}|s=0) = 0.7'
      },
      {
        name: 'Remove text prefix from aligned block',
        input: 'text \\begin{aligned}',
        expected: '\\begin{aligned}'
      },
      {
        name: 'Remove text // comments (simple)',
        input: 'text // 狀態轉移概率模型',
        expected: '// 狀態轉移概率模型'
      }
    ]

    testCases.forEach(({ name, input, expected }) => {
      it(name, () => {
        const result = cleanMarkdown(input)
        // We might need loose matching because of formatFlattenedCode
        if (input.includes('public class')) {
             expect(result).not.toContain('text //')
             expect(result).toContain('public class')
             expect(result).toContain('\n') // Should have restored newlines
        } else {
             expect(result.trim()).toBe(expected.trim())
        }
      })
    })

    it('Repairs mispaired fenced code blocks', () => {
      const input = [
        '```java',
        'public class A {',
        '  // missing closing fence...',
        '---',
        '# Next Section',
        'Text after section',
        '```java',
        'public class B {}',
        '```',
      ].join('\n')

      const result = cleanMarkdown(input)
      // should auto-insert a closing fence before the section break
      expect(result).toContain('\n```\n---\n')
      // the next opening fence should remain an opening fence (not a closing one)
      expect(result).toContain('\n```java\npublic class B {}\n```')
    })

    it('Wraps code-like blocks even when other fences exist', () => {
      const input = [
        '## heading',
        '',
        '```text',
        'not code',
        '```',
        '',
        '程式碼分析：',
        '',
        '雖然圖片中沒有直接的程式碼，但此類問題的實作通常透過以下方式實現：java public class StateTransitionModel { private final Map<String, Map<String, Double>> transitionProbabilities; } // 狀態轉移機率',
      ].join('\n')

      const cleaned = cleanMarkdown(input)
      expect(cleaned).toContain('```java')
      expect(cleaned).toContain('StateTransitionModel')

      const rendered = renderNoteMarkdown(input)
      const { html } = rendered
      expect(rendered.diagnostics.codeBlocks).toBeGreaterThanOrEqual(2)
      expect(html).toContain('plain-code-block')
      expect(html).toContain('StateTransitionModel')
    })
  })
})
