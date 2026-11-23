export function activateButton(event: KeyboardEvent) {
  // #ifdef H5
  if (event.key !== 'Enter' && event.key !== ' ') return
  const target = event.currentTarget
  if (!(target instanceof HTMLElement) || target.hasAttribute('disabled')) return
  event.preventDefault()
  if (!event.repeat) target.click()
  // #endif
}
