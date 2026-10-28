import { atom, read, update } from 'claude-code'
import type { Register, Timer, TurnUsage } from 'claude-code'

const total = atom({ plugin: 'free-token-counter', key: 'total' } as const, 0)
const session = atom({ plugin: 'free-token-counter', key: 'session' } as const, 0)
const tick = atom({ plugin: 'free-token-counter', key: 'tick' } as const, 0)

const PHRASES = [
  'conjured from thin air',
  'brewed at zero cost',
  'liberated from the cloud',
  'spun out of starlight',
  'gifted by the open-source gods',
  'served on the house',
  'harvested for free',
  'minted at $0.00',
  'borrowed from the giants',
  'summoned without a wallet',
]
const COLORS = ['#ff6ec7', '#7df9ff', '#ffd166', '#06d6a0', '#a78bfa', '#f97316']
const SPARKS = ['✦', '✧', '✶', '✷', '✸', '✹']

// Written by the router's usage_logger.py; see its LIMITS table.
type ProviderUsage = {
  requests: number
  tokens: number
  recent: number[]
  limitedAt: number | null
  limit: number | null
  window: 'day' | 'hour'
}
type UsageFile = {
  day: string
  providers: Record<string, ProviderUsage>
  budget?: { total: number; left: number; avgRequest: number }
}

const NAMES: Record<string, string> = {
  openrouter: 'OpenRouter',
  groq: 'Groq',
  gemini: 'Gemini',
  kilo: 'Kilo',
  zai: 'Z.ai',
  llm7: 'LLM7',
  nvidia: 'NVIDIA',
  mistral: 'Mistral',
}
const ORDER = Object.keys(NAMES)
// a provider that answered "limit reached" this recently is shown as resting
const RESTING_MS = 2 * 60 * 1000

function compact(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`
  return String(n)
}

function tokensOf(usage: TurnUsage): number {
  return (
    usage.input_tokens +
    usage.output_tokens +
    usage.cache_read_input_tokens +
    usage.cache_creation_input_tokens
  )
}

function bar(fraction: number, width: number, full = '█', empty = '░'): string {
  const filled = Math.round(Math.min(1, Math.max(0, fraction)) * width)
  return full.repeat(filled) + empty.repeat(width - filled)
}

function levelColor(usedFraction: number): string {
  if (usedFraction >= 0.85) return '#ef4444'
  if (usedFraction >= 0.6) return '#ffd166'
  return '#06d6a0'
}

export const register: Register = on => {
  let ticker: Timer | undefined

  on('session.start', async ($, e, next) => {
    const saved = Number((await $.store.get('total')) ?? 0)
    await update($, total, () => saved)
    ticker?.cancel()
    ticker = $.clock.every(4000, () => {
      void update($, tick, n => n + 1)
    })

    return next(e)
  })

  on('turn.step', async function* ($, e, next) {
    const result = yield* next(e)
    if (result.usage) {
      const spent = tokensOf(result.usage)
      await update($, session, n => n + spent)
      await update($, total, n => n + spent)
      await $.store.set('total', await read($, total))
    }

    return result
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) {
      return next(e)
    }

    const [all, now, n] = await Promise.all([read($, total), read($, session), read($, tick)])
    const { context } = await $.session.usage()
    let usage: UsageFile | undefined
    try {
      usage = JSON.parse(await $.fs.read(`${$.plugin.root}/../../logs/usage.json`))
    } catch {
      usage = undefined
    }

    const { Box, Text } = $.ui.resolve(e)
    const nowMs = Date.now()
    const memoryUsed = (context.percent ?? 0) / 100
    const resting = ORDER.filter(key => {
      const limitedAt = usage?.providers[key]?.limitedAt
      return limitedAt != null && nowMs - limitedAt * 1000 < RESTING_MS
    }).map(key => NAMES[key])

    return (
      <Box flexDirection="column">
        <Box>
          <Text dimColor>memory </Text>
          <Text color={levelColor(memoryUsed)}>{bar(memoryUsed, 20)}</Text>
          <Text dimColor>
            {' '}
            {context.percent ?? 0}% · {compact(context.tokens ?? 0)} of {compact(context.window)}
            {memoryUsed >= 0.85 ? ' · will compact soon' : ''}
          </Text>
        </Box>
        {usage?.budget && usage.budget.total > 0 ? (
          <Box>
            <Text dimColor>today  </Text>
            <Text color={levelColor(1 - usage.budget.left / usage.budget.total)}>
              {bar(usage.budget.left / usage.budget.total, 20, '▰', '▱')}
            </Text>
            <Text dimColor>
              {' '}~{compact(usage.budget.left)} of ~{compact(usage.budget.total)} tokens left
            </Text>
            {resting.length > 0 ? <Text color="#ef4444"> · {resting.join(', ')} resting</Text> : null}
          </Box>
        ) : null}
        <Box>
          <Text color={COLORS[n % COLORS.length]} bold>
            {SPARKS[n % SPARKS.length]} {compact(all)} tokens{' '}
          </Text>
          <Text italic>{PHRASES[n % PHRASES.length]}</Text>
          <Text dimColor> · this session {compact(now)}</Text>
        </Box>
      </Box>
    )
  })
}
