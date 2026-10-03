export function inr(n: number | null | undefined, opts: { decimals?: boolean } = {}): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return '₹' + n.toLocaleString('en-IN', {
    minimumFractionDigits: opts.decimals ? 2 : 0,
    maximumFractionDigits: opts.decimals ? 2 : 0,
  })
}

export function time(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })
}

export function relDay(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const days = Math.round((startOf(d) - startOf(now)) / 86400000)
  if (days === 0) return 'Today'
  if (days === -1) return 'Yesterday'
  if (days === 1) return 'Tomorrow'
  if (days > 1 && days < 31) return `In ${days} days`
  if (days < -1 && days > -31) return `${-days} days ago`
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function dateTime(iso: string): string {
  return `${relDay(iso)}, ${time(iso)}`
}

function startOf(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
}

export function ago(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

export function greeting(): string {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'
}

export const TIER_TEXT: Record<string, { short: string; long: string }> = {
  TIER_1: { short: 'Tier 1 · Auto', long: 'Safe to do automatically' },
  TIER_2: { short: 'Tier 2 · Approval', long: 'Your approval is required' },
  TIER_3: { short: 'Tier 3 · Escalate', long: 'Human review recommended' },
}

export const PARTNER_SHORT: Record<string, string> = {
  axis: 'Axis', icici: 'ICICI', hdfc: 'HDFC', sbi: 'SBI', aa: 'Account Aggregator', nsdl: 'PAN registry',
}

export const BANKS: { id: string; name: string; color: string; short: string; dialect: string }[] = [
  { id: 'hdfc', name: 'HDFC Bank', color: '#004c8f', short: 'HDFC', dialect: 'JSON envelope API' },
  { id: 'icici', name: 'ICICI Bank', color: '#b02a30', short: 'ICICI', dialect: 'NPCI NACH API' },
  { id: 'sbi', name: 'SBI', color: '#22409a', short: 'SBI', dialect: 'JSON envelope API' },
  { id: 'axis', name: 'Axis Bank', color: '#97144d', short: 'AXIS', dialect: 'NPCI NACH API' },
]

export const bankMeta = (id: string) => BANKS.find(b => b.id === id) ?? { id, name: id, color: '#44546c', short: id.toUpperCase(), dialect: '' }

const FUND_COLORS = ['#0a5bd3', '#12965a', '#c97a00', '#7a3fd1', '#0e8fb3', '#d63c2b', '#2f6f5e', '#5a6b85']
export const fundColor = (id: string) => FUND_COLORS[[...id].reduce((a, c) => a + c.charCodeAt(0), 0) % FUND_COLORS.length]

export function dueLabel(isoDate: string): string {
  const d = new Date(isoDate + 'T00:00:00')
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}
