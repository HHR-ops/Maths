declare global {
  interface Window {
    __SURVEY_TOKEN__?: string
    __surveyDirty?: boolean
    __surveyWorkspace?: unknown
    pywebview?: { api?: { save_file: (content: string, name: string) => Promise<{ ok: boolean; cancelled?: boolean; error?: string }> } }
  }
}
export async function rpc<T>(op: string, payload: unknown = {}): Promise<T> {
  const reply = await fetch('/api', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Survey-Token': window.__SURVEY_TOKEN__ || '' }, body: JSON.stringify({ op, payload }) })
  const result = await reply.json()
  if (!result.ok) throw new Error(result.error || '计算服务未响应。')
  return result.data
}
export async function saveFile(content: string, filename: string): Promise<boolean> {
  const native = window.pywebview?.api
  if (native) {
    const result = await native.save_file(content, filename)
    if (!result.ok) throw new Error(result.error)
    return !result.cancelled
  }
  const url = URL.createObjectURL(new Blob([filename.endsWith('.csv') ? '\uFEFF'+content : content], { type: 'text/plain;charset=utf-8' }))
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  return true
}
export const json = (value: unknown) => JSON.stringify(value, null, 2)
