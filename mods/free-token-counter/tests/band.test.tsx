import { expect, test } from 'claude-code/testing'

const USAGE = {
  day: '2026-10-28',
  providers: {
    openrouter: { requests: 30, tokens: 9000, recent: [], limitedAt: null, limit: 50, window: 'day' },
    gemini: { requests: 7, tokens: 2000, recent: [], limitedAt: null, limit: null, window: 'day' },
    groq: { requests: 5, tokens: 500, recent: [], limitedAt: Date.now() / 1000, limit: 2000, window: 'day' },
  },
  budget: { total: 153400000, left: 120000000, avgRequest: 30000 },
}

test('the band shows memory, one token bar, and the total', async ($, on) => {
  on('store.get', () => ({ value: 1234567 }))
  on('store.set', () => ({ value: undefined }))
  on('clock.every', () => ({ value: undefined }))
  on('fs.read', () => ({ value: JSON.stringify(USAGE) }))
  on('session.usage', () => ({
    value: { startedAt: 0, context: { tokens: 64000, window: 128000, percent: 50 }, rateLimits: [] },
  }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))

  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })

  const ui = await $.ui.mount({
    plugin: 'free-token-counter',
    component: 'AbovePrompt',
    surface: 'terminal',
    props: { hasSurvey: false, isWorking: false, maxRows: 10 },
  })

  expect((await ui.find({ type: 'Text', text: /50% · 64\.0K of 128\.0K/ }))?.text).toContain('64.0K')
  expect((await ui.find({ type: 'Text', text: /tokens left/ }))?.text).toContain('~120.00M of ~153.40M tokens left')
  expect((await ui.find({ type: 'Text', text: /resting/ }))?.text).toContain('Groq resting')
  expect((await ui.find({ type: 'Text', text: /tokens $/ }))?.text).toContain('1.23M tokens')
  await ui.unmount()
})
