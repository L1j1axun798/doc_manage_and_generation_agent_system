export const SESSION_REPLACED_EVENT = 'wind-doc:session-replaced'

let sessionReplacedPending = false

export function notifySessionReplaced(): void {
  sessionReplacedPending = true
  window.dispatchEvent(new Event(SESSION_REPLACED_EVENT))
}

export function consumePendingSessionReplacement(): boolean {
  const pending = sessionReplacedPending
  sessionReplacedPending = false
  return pending
}
