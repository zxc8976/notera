// Vitest config in JS to avoid TS type resolution issues
/** @type {import('vitest').UserConfig} */
export default {
  test: {
    environment: 'jsdom',
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
    },
  },
}
