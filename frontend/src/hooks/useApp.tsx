import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, setApiUser } from '../services/api'
import type { Overview } from '../services/types'

export type Tab = 'home' | 'invest' | 'saarthi' | 'loans'
export type Route =
  | { name: 'journey'; id: string; autoApprove?: boolean }
  | { name: 'journeys' }
  | { name: 'knowledge' }
  | { name: 'fund'; id: string }
  | { name: 'linkBank' }
  | { name: 'apply'; kind: string; partnerId?: string }
  | { name: 'banks' }
  | { name: 'profile' }

interface ChatState { open: boolean; journeyId?: string; preset?: string }

interface AppCtx {
  userId: string | null
  signIn: (id: string) => void
  signOut: () => void
  tab: Tab
  setTab: (t: Tab) => void
  stack: Route[]
  push: (r: Route) => void
  pop: () => void
  replace: (r: Route) => void
  overview: Overview | null
  refresh: () => Promise<void>
  version: number
  bump: () => void
  chat: ChatState
  openChat: (journeyId?: string, preset?: string) => void
  closeChat: () => void
  focusJourney: string | null
  setFocusJourney: (id: string | null) => void
  toast: string | null
  showToast: (t: string) => void
}

const Ctx = createContext<AppCtx | null>(null)
const KEY = 'saarthi.user'

function readUser(): string | null {
  try { return window.localStorage.getItem(KEY) } catch { return null }
}
function writeUser(id: string | null) {
  try { if (id) window.localStorage.setItem(KEY, id); else window.localStorage.removeItem(KEY) } catch { /* storage unavailable */ }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [userId, setUserId] = useState<string | null>(() => { const u = readUser(); setApiUser(u); return u })
  const [tab, setTabState] = useState<Tab>('home')
  const [stack, setStack] = useState<Route[]>([])
  const [overview, setOverview] = useState<Overview | null>(null)
  const [version, setVersion] = useState(0)
  const [chat, setChat] = useState<ChatState>({ open: false })
  const [focusJourney, setFocusJourney] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const signIn = useCallback((id: string) => {
    setApiUser(id); writeUser(id); setUserId(id); setStack([]); setTabState('home'); setOverview(null); setFocusJourney(null)
  }, [])
  const signOut = useCallback(() => {
    setApiUser(null); writeUser(null); setUserId(null); setStack([]); setOverview(null); setFocusJourney(null)
  }, [])

  const refresh = useCallback(async () => {
    if (!userId) return
    try { setOverview(await api.overview()) } catch (e) {
      if ((e as { status?: number }).status === 401) signOut()
      else console.error(e)
    }
  }, [userId, signOut])

  useEffect(() => { refresh() }, [refresh, version])

  const bump = useCallback(() => setVersion(v => v + 1), [])
  const push = useCallback((r: Route) => {
    setStack(s => [...s, r])
    if (r.name === 'journey') setFocusJourney(r.id)
  }, [])
  const replace = useCallback((r: Route) => {
    setStack(s => [...s.slice(0, -1), r])
    if (r.name === 'journey') setFocusJourney(r.id)
  }, [])
  const pop = useCallback(() => setStack(s => s.slice(0, -1)), [])
  const setTab = useCallback((t: Tab) => { setStack([]); setTabState(t) }, [])
  const showToast = useCallback((t: string) => {
    setToast(t)
    window.setTimeout(() => setToast(null), 3200)
  }, [])

  const value = useMemo<AppCtx>(() => ({
    userId, signIn, signOut, tab, setTab, stack, push, pop, replace, overview, refresh, version, bump, chat,
    openChat: (journeyId, preset) => setChat({ open: true, journeyId, preset }),
    closeChat: () => setChat({ open: false }),
    focusJourney, setFocusJourney, toast, showToast,
  }), [userId, signIn, signOut, tab, setTab, stack, push, pop, replace, overview, refresh, version, bump, chat, focusJourney, toast, showToast])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useApp() {
  const c = useContext(Ctx)
  if (!c) throw new Error('useApp outside provider')
  return c
}

/** Fetch helper that re-runs whenever the global data version changes. */
export function useData<T>(loader: () => Promise<T>, deps: unknown[] = []) {
  const { version } = useApp()
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const load = useCallback(async () => {
    try { setData(await loader()); setError(null) } catch (e) { setError((e as Error).message) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(() => { load() }, [load, version])
  return { data, setData, error, reload: load }
}
