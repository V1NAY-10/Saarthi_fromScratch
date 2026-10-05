import { AnimatePresence, motion } from 'framer-motion'
import { Info } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { BottomNav } from './components/BottomNav'
import { JourneyScreen } from './features/journey/JourneyScreen'
import { AppProvider, useApp } from './hooks/useApp'
import { Banks, LinkBank } from './pages/Banks'
import { Chat } from './pages/Chat'
import { EnginePanel } from './pages/EnginePanel'
import { FundDetail } from './pages/FundDetail'
import { Home } from './pages/Home'
import { Invest } from './pages/Invest'
import { Apply } from './pages/Apply'
import { Loans } from './pages/Loans'
import { Onboarding } from './pages/Onboarding'
import { Plan } from './pages/Plan'
import { SaarthiHub } from './pages/SaarthiHub'
import { Vault } from './pages/Vault'
import { JourneysList, Knowledge, Profile } from './pages/Secondary'

function Screen() {
  const { userId, tab, stack, chat, toast } = useApp()
  const top = stack[stack.length - 1]
  const key = !userId ? 'onboarding' : top ? `${top.name}-${'id' in top ? top.id : 'kind' in top ? top.kind : ''}-${stack.length}` : tab
  const scroller = useRef<HTMLDivElement>(null)
  useEffect(() => { scroller.current?.scrollTo({ top: 0 }) }, [key])

  let content
  if (!userId) content = <Onboarding />
  else if (top?.name === 'journey') content = <JourneyScreen id={top.id} autoApprove={top.autoApprove} />
  else if (top?.name === 'journeys') content = <JourneysList />
  else if (top?.name === 'knowledge') content = <Knowledge />
  else if (top?.name === 'fund') content = <FundDetail id={top.id} />
  else if (top?.name === 'linkBank') content = <LinkBank />
  else if (top?.name === 'apply') content = <Apply kind={top.kind} partnerId={top.partnerId} />
  else if (top?.name === 'banks') content = <Banks />
  else if (top?.name === 'profile') content = <Profile />
  else if (top?.name === 'vault') content = <Vault />
  else content = { home: <Home />, invest: <Invest />, saarthi: <SaarthiHub />, plan: <Plan />, loans: <Loans /> }[tab]

  const now = new Date()
  return (
    <div className="phone">
      <div className="phone-notch" />
      <div className="statusbar"><span className="num">{now.getHours()}:{String(now.getMinutes()).padStart(2, '0')}</span><span>5G ▮▮▮ 86%</span></div>
      <div className="screen" ref={scroller}>
        {/* Enter-only page transition: an exit animation with mode="wait" can stall when the
            leaving page still has nested animations running, leaving a blank screen. */}
        <motion.div key={key} initial={{ opacity: 0, x: top ? 18 : 0 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.18 }} style={{ minHeight: '100%' }}>
          {content}
        </motion.div>
      </div>
      {userId && !top && <BottomNav />}
      <AnimatePresence>{userId && chat.open && <Chat />}</AnimatePresence>
      <AnimatePresence>
        {toast && <motion.div className="toast" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}><Info size={16} />{toast}</motion.div>}
      </AnimatePresence>
    </div>
  )
}

export default function App() {
  return (
    <AppProvider>
      <div className="stage">
        <EnginePanel />
        <Screen />
      </div>
    </AppProvider>
  )
}
