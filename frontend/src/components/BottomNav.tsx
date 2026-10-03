import { Home, Landmark, TrendingUp, UserRound } from 'lucide-react'
import { useApp, type Tab } from '../hooks/useApp'
import { SaarthiMark } from './ui'

const ITEMS: { key: Tab; label: string; Icon?: typeof Home }[] = [
  { key: 'home', label: 'Home', Icon: Home },
  { key: 'invest', label: 'Invest', Icon: TrendingUp },
  { key: 'saarthi', label: 'Saarthi' },
  { key: 'banks', label: 'Banks', Icon: Landmark },
  { key: 'profile', label: 'Profile', Icon: UserRound },
]

export function BottomNav() {
  const { tab, setTab, stack, overview } = useApp()
  const attention = overview?.attention.length ?? 0
  return (
    <nav className="bottomnav">
      {ITEMS.map(({ key, label, Icon }) => {
        const active = tab === key && stack.length === 0
        if (!Icon) {
          return (
            <button key={key} className={`nav-item nav-saarthi ${active ? 'active' : ''}`} onClick={() => setTab(key)}>
              <span className="nav-orb"><SaarthiMark size={26} /></span>
              {label}
              {attention > 0 && <span className="nav-badge">{attention}</span>}
            </button>
          )
        }
        return (
          <button key={key} className={`nav-item ${active ? 'active' : ''}`} onClick={() => setTab(key)}>
            <Icon size={21} strokeWidth={active ? 2.4 : 2} />
            {label}
          </button>
        )
      })}
    </nav>
  )
}
