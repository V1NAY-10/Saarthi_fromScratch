import { motion } from 'framer-motion'
import { ArrowLeft, ChevronRight, Headset, Send } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { CheckRow, SaarthiMark, TierBadge } from '../components/ui'
import { useApp } from '../hooks/useApp'
import { api } from '../services/api'
import type { ChatCard } from '../services/types'

interface Msg { from: 'user' | 'bot'; text?: string; card?: ChatCard }

const SUGGEST: Record<string, string[]> = {
  default: ['What needs my attention?', 'Why did my SIP fail?', 'Is my money safe?', 'Why is my bank account not verified?'],
  investment: ['Why did my SIP fail?', 'Is my money safe?', 'Fix it', 'Why is my Journey Health this low?'],
  bank_account: ['Why is my bank account not verified?', 'Is my money safe?', 'Fix it', 'Talk to a human'],
}

export function Chat() {
  const { chat, closeChat, push, overview } = useApp()
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [focus, setFocus] = useState<string | undefined>(chat.journeyId)
  const body = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const j = overview?.journeys.find(x => x.id === chat.journeyId)
    setMsgs([{ from: 'bot', text: j ? `I'm looking at your ${j.title}. Ask me anything about it — I'll answer only from verified journey data.` : `Hi ${overview?.user.name.split(' ')[0] ?? ''}. I know every step of your financial journeys. What would you like to understand?` }])
    setFocus(chat.journeyId)
    if (chat.preset) send(chat.preset)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chat.journeyId, chat.preset])

  useEffect(() => { body.current?.scrollTo({ top: body.current.scrollHeight, behavior: 'smooth' }) }, [msgs, typing])

  async function send(text: string) {
    if (!text.trim()) return
    setInput('')
    setMsgs(m => [...m, { from: 'user', text }])
    setTyping(true)
    try {
      const r = await api.chat(text, focus)
      if (r.journey_id) setFocus(r.journey_id)
      await new Promise(res => setTimeout(res, 450))
      setMsgs(m => [...m, ...r.messages.map(t => ({ from: 'bot' as const, text: t })), ...r.cards.filter(c => c.type !== 'journey' || r.cards.length === 1).map(c => ({ from: 'bot' as const, card: c }))])
    } catch (e) {
      setMsgs(m => [...m, { from: 'bot', text: `Sorry — ${(e as Error).message}` }])
    } finally { setTyping(false) }
  }

  function open(jid: string, autoApprove = false) {
    closeChat()
    push({ name: 'journey', id: jid, autoApprove })
  }

  return (
    <motion.div className="full" initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }} transition={{ type: 'spring', damping: 32, stiffness: 320 }}>
      <div className="topbar" style={{ paddingTop: 54, background: 'var(--surface)', borderBottom: '1px solid var(--line)' }}>
        <button className="icon-btn" onClick={closeChat} aria-label="Close"><ArrowLeft size={18} /></button>
        <SaarthiMark size={30} />
        <div className="grow"><h1>Saarthi</h1><div className="sub">Grounded in your journey data</div></div>
      </div>
      <div className="chat-body" ref={body}>
        {msgs.map((m, i) => m.text ? (
          <motion.div key={i} className={`msg ${m.from}`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>{m.text}</motion.div>
        ) : m.card ? (
          <motion.div key={i} className="msg-card" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
            <CardView card={m.card} onOpen={open} />
          </motion.div>
        ) : null)}
        {typing && <div className="msg bot"><span className="typing"><i /><i /><i /></span></div>}
      </div>
      <div className="suggest">
        {(SUGGEST[overview?.journeys.find(x => x.id === focus)?.category ?? 'default'] ?? SUGGEST.default).map(s => <button key={s} onClick={() => send(s)}>{s}</button>)}
      </div>
      <form className="chat-input" onSubmit={e => { e.preventDefault(); send(input) }}>
        <input value={input} onChange={e => setInput(e.target.value)} placeholder="Ask about your journeys…" />
        <button className="btn btn-primary" style={{ width: 44, padding: 0, height: 44 }} aria-label="Send"><Send size={17} /></button>
      </form>
    </motion.div>
  )
}

function CardView({ card, onOpen }: { card: ChatCard; onOpen: (id: string, auto?: boolean) => void }) {
  if (card.type === 'approval') {
    return (
      <div className="card card-pad card-saarthi">
        <div className="between"><div className="eyebrow">Recovery ready</div>{card.tier && <TierBadge tier={card.tier} />}</div>
        <div style={{ fontWeight: 700, fontSize: 14, marginTop: 6 }}>{card.title}</div>
        <div style={{ marginTop: 6 }}>{card.checks?.slice(0, 4).map(c => <CheckRow key={c} passed label={c} />)}</div>
        <button className="btn btn-primary btn-block" style={{ marginTop: 8 }} onClick={() => onOpen(card.journey_id, true)}>Review & Approve</button>
      </div>
    )
  }
  if (card.type === 'escalate') {
    return (
      <div className="card card-pad">
        <div className="row"><Headset size={16} color="var(--warn)" /><div style={{ fontWeight: 700 }}>Human specialist recommended</div></div>
        {card.reasons?.map(r => <div key={r} className="muted" style={{ fontSize: 12, marginTop: 4 }}>• {r}</div>)}
        <button className="btn btn-warn btn-block btn-sm" style={{ marginTop: 10 }} onClick={() => onOpen(card.journey_id)}>Review & escalate</button>
      </div>
    )
  }
  const label = card.type === 'decision' ? 'See diagnosis & recovery' : card.type === 'health' ? `See all health factors (${card.score})` : `Open ${card.title}`
  return (
    <button className="card list-row tap" style={{ width: '100%', textAlign: 'left' }} onClick={() => onOpen(card.journey_id)}>
      <SaarthiMark size={20} />
      <div className="grow t" style={{ fontSize: 13 }}>{label}</div>
      {card.tier && <TierBadge tier={card.tier} />}
      <ChevronRight size={16} className="muted" />
    </button>
  )
}
