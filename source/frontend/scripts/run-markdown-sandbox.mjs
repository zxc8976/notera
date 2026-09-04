import { readFileSync } from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import { performance } from 'perf_hooks'
import { JSDOM } from 'jsdom'
import createDOMPurify from 'dompurify'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

if (typeof globalThis.window === 'undefined') {
  const { window } = new JSDOM('<!DOCTYPE html><html><body></body></html>')
  globalThis.window = window
  globalThis.document = window.document
}

if (!globalThis.window.DOMPurify) {
  globalThis.window.DOMPurify = createDOMPurify(globalThis.window)
}

const { renderNoteMarkdown } = await import('../src/utils/markdownRenderer.js')

const args = process.argv.slice(2)
const inputPath = args[0]
const absolutePath = inputPath
  ? path.resolve(process.cwd(), inputPath)
  : path.resolve(__dirname, '../../../docs/NOTE_OUTPUT_OPTIMIZED_PROMPT.md')

const markdown = readFileSync(absolutePath, 'utf-8')

const start = performance.now()
const { html, diagnostics } = renderNoteMarkdown(markdown, {
  translate: (key) => key,
  measure: true,
})
const end = performance.now()

const report = {
  input: absolutePath,
  renderMs: diagnostics.renderMs,
  totalTimeMs: Number((end - start).toFixed(2)),
  codeBlocks: diagnostics.codeBlocks,
  copyButtons: diagnostics.injectedButtons,
  warnings: diagnostics.warnings,
  outputLength: html.length,
}

console.log(JSON.stringify(report, null, 2))
