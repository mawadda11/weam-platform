import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiClient, tokenStorage } from '../api/client'
import type {
  CareConversation,
  CareTeamMember,
  CareTeamOverview,
  ChatMessage,
  ChildProfile,
} from '../types'
import '../styles/communication-hub.css'

const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'
const wsBase = apiUrl.replace(/^http/, 'ws').replace(/\/api\/v1\/?$/, '')

export default function CommunicationHubPage() {
  const { childId } = useParams()
  const [child, setChild] = useState<ChildProfile | null>(null)
  const [team, setTeam] = useState<CareTeamOverview | null>(null)
  const [conversations, setConversations] = useState<CareConversation[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [body, setBody] = useState('')
  const [newOpen, setNewOpen] = useState(false)
  const [kind, setKind] = useState<'direct' | 'group'>('direct')
  const [title, setTitle] = useState('')
  const [selectedUsers, setSelectedUsers] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const socketRef = useRef<WebSocket | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  const selected = conversations.find((conversation) => conversation.id === selectedId) ?? null
  const currentUserId = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem('weam_user') || '{}').id as string | undefined
    } catch {
      return undefined
    }
  }, [])

  const availableMembers = useMemo(
    () =>
      (team?.members ?? []).filter(
        (member) =>
          member.user_id !== currentUserId &&
          member.access_status === 'active' &&
          (member.is_primary_guardian || member.permissions.includes('message_team')),
      ),
    [team, currentUserId],
  )

  const loadConversations = async () => {
    if (!childId) return
    const response = await apiClient.get<CareConversation[]>(
      `/children/${childId}/conversations`,
    )
    setConversations(response.data)
    if (!selectedId && response.data.length) {
      setSelectedId(response.data[0].id)
    }
  }

  useEffect(() => {
    if (!childId) return
    Promise.all([
      apiClient.get<ChildProfile>(`/children/${childId}`),
      apiClient.get<CareTeamOverview>(`/children/${childId}/care-team`),
    ])
      .then(([childResponse, teamResponse]) => {
        setChild(childResponse.data)
        setTeam(teamResponse.data)
        return loadConversations()
      })
      .catch(() => setError('تعذر فتح مركز التواصل أو لا توجد لديك صلاحية المراسلة.'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [childId])

  useEffect(() => {
    if (!selectedId) {
      setMessages([])
      return
    }

    apiClient
      .get<ChatMessage[]>(`/conversations/${selectedId}/messages`)
      .then((response) => setMessages(response.data))
      .catch(() => setError('تعذر تحميل الرسائل.'))

    socketRef.current?.close()
    const socket = new WebSocket(`${wsBase}/api/v1/ws/conversations/${selectedId}`)
    socketRef.current = socket

    socket.onopen = () => {
      socket.send(
        JSON.stringify({
          type: 'auth',
          token: tokenStorage.getAccessToken(),
        }),
      )
    }

    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data)
      if (payload.type === 'message') {
        const incoming = payload.message as ChatMessage
        setMessages((current) =>
          current.some((item) => item.id === incoming.id)
            ? current
            : [...current, incoming],
        )
        void loadConversations()
      }
    }

    return () => socket.close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (event: FormEvent) => {
    event.preventDefault()
    if (!selectedId || !body.trim()) return
    const content = body.trim()
    setBody('')
    setBusy(true)
    try {
      const response = await apiClient.post<ChatMessage>(
        `/conversations/${selectedId}/messages`,
        { body: content },
      )
      setMessages((current) =>
        current.some((item) => item.id === response.data.id)
          ? current
          : [...current, response.data],
      )
      await loadConversations()
    } catch {
      setBody(content)
      setError('تعذر إرسال الرسالة.')
    } finally {
      setBusy(false)
    }
  }

  const createConversation = async (event: FormEvent) => {
    event.preventDefault()
    if (!childId) return

    if (kind === 'direct' && selectedUsers.length !== 1) {
      setError('اختاري شخصًا واحدًا للمحادثة الفردية.')
      return
    }
    if (kind === 'group' && selectedUsers.length < 1) {
      setError('اختاري عضوًا واحدًا على الأقل للمجموعة.')
      return
    }

    setBusy(true)
    setError('')
    try {
      const response = await apiClient.post<CareConversation>(
        `/children/${childId}/conversations`,
        {
          kind,
          title: kind === 'group' ? title || null : null,
          participant_user_ids: selectedUsers,
        },
      )
      setNewOpen(false)
      setSelectedUsers([])
      setTitle('')
      await loadConversations()
      setSelectedId(response.data.id)
    } catch (requestError: any) {
      setError(
        requestError?.response?.data?.detail ||
          'تعذر إنشاء المحادثة.',
      )
    } finally {
      setBusy(false)
    }
  }

  const toggleUser = (userId: string) => {
    if (kind === 'direct') {
      setSelectedUsers([userId])
      return
    }
    setSelectedUsers((current) =>
      current.includes(userId)
        ? current.filter((item) => item !== userId)
        : [...current, userId],
    )
  }

  if (!child && !error) {
    return <div className="loading-row"><div className="spinner" /> جاري فتح مركز التواصل...</div>
  }

  if (!child) {
    return <div className="prototype-empty-card"><h2>تعذر فتح التواصل</h2><p>{error}</p><Link className="btn btn-primary" to="/dashboard">الرئيسية</Link></div>
  }

  return (
    <section className="communication-page">
      <div className="communication-heading">
        <div>
          <Link className="communication-back" to={`/children/${child.id}`}>← العودة لملف الطفل</Link>
          <span className="soft-kicker">Communication Hub</span>
          <h1>تواصل فريق {child.preferred_name || child.first_name}</h1>
          <p>محادثات فردية ومجموعات خاصة بأعضاء فريق الرعاية المصرح لهم فقط.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setNewOpen(true)}>＋ محادثة جديدة</button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {newOpen && (
        <form className="new-conversation-card" onSubmit={createConversation}>
          <div className="new-conversation-head">
            <div><span className="soft-kicker">محادثة جديدة</span><h2>من تريدين إضافته؟</h2></div>
            <button type="button" className="text-action" onClick={() => setNewOpen(false)}>إغلاق</button>
          </div>

          <div className="conversation-kind-switch">
            <button type="button" className={kind === 'direct' ? 'active' : ''} onClick={() => { setKind('direct'); setSelectedUsers([]) }}>فردية</button>
            <button type="button" className={kind === 'group' ? 'active' : ''} onClick={() => { setKind('group'); setSelectedUsers([]) }}>مجموعة</button>
          </div>

          {kind === 'group' && (
            <label className="field"><span>اسم المجموعة</span><input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="مثال: فريق متابعة تاليا" /></label>
          )}

          <div className="conversation-member-grid">
            {availableMembers.map((member) => (
              <label key={member.user_id} className={selectedUsers.includes(member.user_id) ? 'selected' : ''}>
                <input type={kind === 'direct' ? 'radio' : 'checkbox'} name="conversation-member" checked={selectedUsers.includes(member.user_id)} onChange={() => toggleUser(member.user_id)} />
                <span className="member-dot">{member.full_name.slice(0, 1)}</span>
                <span><strong>{member.full_name}</strong><small>{member.role_label || 'عضو فريق الرعاية'}</small></span>
              </label>
            ))}
          </div>

          <button className="btn btn-primary" disabled={busy || !availableMembers.length}>
            {busy ? 'جارٍ الإنشاء...' : 'إنشاء المحادثة'}
          </button>
        </form>
      )}

      <div className="communication-shell">
        <aside className="conversation-sidebar">
          <div className="conversation-sidebar-title">
            <span>المحادثات</span>
            <strong>{conversations.length}</strong>
          </div>

          {!conversations.length ? (
            <div className="conversation-empty-small"><span>💬</span><p>لا توجد محادثات بعد.</p></div>
          ) : (
            conversations.map((conversation) => (
              <button
                key={conversation.id}
                className={`conversation-list-item ${selectedId === conversation.id ? 'active' : ''}`}
                onClick={() => setSelectedId(conversation.id)}
              >
                <span className="conversation-avatar">{conversation.kind === 'group' ? '♧' : conversation.title.slice(0, 1)}</span>
                <span className="conversation-list-copy">
                  <strong>{conversation.title}</strong>
                  <small>{conversation.last_message?.body || (conversation.kind === 'group' ? 'مجموعة فريق الرعاية' : 'ابدؤوا المحادثة')}</small>
                </span>
                <time>{conversation.last_message ? new Date(conversation.last_message.created_at).toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' }) : ''}</time>
              </button>
            ))
          )}
        </aside>

        <main className="conversation-main">
          {!selected ? (
            <div className="conversation-empty-main"><span>💬</span><h2>اختاري محادثة</h2><p>أو أنشئي محادثة جديدة مع فريق الرعاية.</p></div>
          ) : (
            <>
              <header className="conversation-chat-head">
                <div><h2>{selected.title}</h2><p>{selected.participants.map((participant) => participant.full_name).join(' · ')}</p></div>
                <span>{selected.kind === 'group' ? `${selected.participants.length} أعضاء` : 'محادثة فردية'}</span>
              </header>

              <div className="conversation-messages">
                {!messages.length && <div className="conversation-start"><span>✦</span><h3>ابدؤوا أول تحديث</h3><p>كل رسالة هنا مرتبطة بفريق رعاية الطفل وليست محادثة عامة.</p></div>}
                {messages.map((message) => {
                  const mine = message.sender_user_id === currentUserId
                  return (
                    <div className={`message-row ${mine ? 'mine' : ''}`} key={message.id}>
                      <div className="message-bubble">
                        {!mine && <strong>{message.sender_name}</strong>}
                        <p dir="auto">{message.body}</p>
                        <time>{new Date(message.created_at).toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' })}</time>
                      </div>
                    </div>
                  )
                })}
                <div ref={bottomRef} />
              </div>

              <form className="conversation-composer" onSubmit={send}>
                <textarea
                  rows={2}
                  dir="auto"
                  value={body}
                  onChange={(event) => setBody(event.target.value)}
                  placeholder="اكتبي تحديثًا للفريق..."
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault()
                      event.currentTarget.form?.requestSubmit()
                    }
                  }}
                />
                <button className="btn btn-primary" disabled={busy || !body.trim()}>إرسال</button>
              </form>
            </>
          )}
        </main>
      </div>
    </section>
  )
}
