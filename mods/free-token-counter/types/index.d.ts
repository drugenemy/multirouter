export type Count = number

declare module 'claude-code' {
  interface PluginState {
    'free-token-counter': { total: Count; session: Count; tick: Count }
  }
}
