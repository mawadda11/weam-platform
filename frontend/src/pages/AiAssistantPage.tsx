import { FormEvent, useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiClient } from '../api/client'
import type {
  AssistantAnswer,
  AssistantMessage,
  AssistantThread,
  ChildProfile,
} from '../types'
import '../styles/ai-assistant.css'

const suggestedQuestions = [
  'لخص لي آخر المعلومات المهمة في ملف الطفل',
  'ما الأهداف الحالية ونسبة التقدم؟',
  'ما أهم الاحتياجات المذكورة في التقارير؟',
  'ما إجراءات المتابعة القادمة؟',
]


function renderAssistantContent(content: string) {
  const lines = content
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)

  const nodes: ReactNode[] = []
  let bullets: string[] = []

  const flushBullets = () => {
    if (!bullets.length) return
    nodes.push(
      <ul className="assistant-answer-list" key={`list-${nodes.length}`}>
        {bullets.map((item, index) => (
          <li dir="auto" key={`${item}-${index}`}>{item}</li>
        ))}
      </ul>,
    )
    bullets = []
  }

  lines.forEach((line) => {
    if (/^[•\-]\s*/.test(line)) {
      bullets.push(line.replace(/^[•\-]\s*/, ''))
      return
    }

    flushBullets()
    const isSafety = line.includes('لا يقدّم تشخيصًا طبيًا')
    const isHeading = /[:：]$/.test(line) && line.length < 70
    nodes.push(
      isSafety
        ? <p className="assistant-answer-safety" dir="auto" key={`s-${nodes.length}`}>{line}</p>
        : isHeading
          ? <strong className="assistant-answer-heading" dir="auto" key={`h-${nodes.length}`}>{line}</strong>
          : <p className="assistant-answer-paragraph" dir="auto" key={`p-${nodes.length}`}>{line}</p>,
    )
  })

  flushBullets()
  return nodes
}


function displayThreadTitle(title: string) {
  const normalized = title
    .replace(/[أإآ]/g, 'ا')
    .replace(/ة/g, 'ه')
    .replace(/ى/g, 'ي')

  if (title === 'محادثة جديدة مع مساعد وئام') return 'محادثة جديدة'
  if (/لخص|ملخص|اخر المعلومات|الوضع/.test(normalized)) return 'ملخص ملف الطفل'
  if (/هدف|اهداف|التقدم|نسبه التقدم/.test(normalized)) return 'الأهداف والتقدم'
  if (/تقرير|تقارير|النتائج/.test(normalized)) return 'آخر التقارير'
  if (/صوت|ملاحظه صوتيه|ملاحظات صوتيه/.test(normalized)) return 'الملاحظات الصوتية'
  if (/متابعه|القادمه|التالي|موعد/.test(normalized)) return 'المتابعة القادمة'
  if (/احتياج|احتياجات|يحتاج/.test(normalized)) return 'الاحتياجات الحالية'
  return title.length > 42 ? `${title.slice(0, 42)}…` : title
}

function sourceTypeLabel(type: string) {
  if (type === 'report') return 'تقرير معتمد'
  if (type === 'goal') return 'هدف'
  if (type === 'voice') return 'ملاحظة صوتية معتمدة'
  if (type === 'profile') return 'ملف الطفل'
  return 'مصدر معتمد'
}

function cleanSourceSnippet(snippet: string) {
  return snippet
    .replace(/\bcompleted\b/gi, 'مكتمل')
    .replace(/\bin_progress\b/gi, 'قيد التنفيذ')
    .replace(/\bnot_started\b/gi, 'لم يبدأ')
    .replace(/\bpaused\b/gi, 'متوقف مؤقتًا')
    .replace(/\s*\|\s*/g, ' • ')
    .replace(/Synthetic test document[^.\n]*/gi, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}


export default function AiAssistantPage() {
  const { childId } = useParams()
  const [child, setChild] = useState<ChildProfile | null>(null)
  const [threads, setThreads] = useState<AssistantThread[]>([])
  const [threadId, setThreadId] = useState<string | null>(null)
  const [messages, setMessages] = useState<AssistantMessage[]>([])
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [deletingThreadId, setDeletingThreadId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const bottomRef = useRef<HTMLDivElement | null>(null)

  const loadThreads = async () => {
    if (!childId) return
    const response = await apiClient.get<AssistantThread[]>(
      `/children/${childId}/assistant/threads`,
    )
    setThreads(response.data)
    if (!threadId && response.data.length) {
      setThreadId(response.data[0].id)
    }
  }

  useEffect(() => {
    if (!childId) return
    Promise.all([
      apiClient.get<ChildProfile>(`/children/${childId}`),
      apiClient.get<AssistantThread[]>(`/children/${childId}/assistant/threads`),
    ])
      .then(([childResponse, threadResponse]) => {
        setChild(childResponse.data)
        setThreads(threadResponse.data)
        if (threadResponse.data.length) {
          setThreadId(threadResponse.data[0].id)
        }
      })
      .catch(() => setError('تعذر فتح مساعد وئام أو لا توجد صلاحية للوصول إلى ملف الطفل.'))
  }, [childId])

  useEffect(() => {
    if (!threadId) {
      setMessages([])
      return
    }
    apiClient
      .get<AssistantMessage[]>(`/assistant/threads/${threadId}/messages`)
      .then((response) => setMessages(response.data))
      .catch(() => setError('تعذر تحميل المحادثة.'))
  }, [threadId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const createThread = async () => {
    if (!childId) return null
    const response = await apiClient.post<AssistantThread>(
      `/children/${childId}/assistant/threads`,
      {},
    )
    await loadThreads()
    setThreadId(response.data.id)
    setMessages([])
    return response.data.id
  }


  const deleteThread = async (thread: AssistantThread) => {
    if (deletingThreadId) return

    const label = displayThreadTitle(thread.title)
    const confirmed = window.confirm(`حذف محادثة «${label}»؟\nلن يمكن استرجاع الرسائل بعد الحذف.`)
    if (!confirmed) return

    setDeletingThreadId(thread.id)
    setError('')

    try {
      await apiClient.delete(`/assistant/threads/${thread.id}`)

      const remaining = threads.filter((item) => item.id !== thread.id)
      setThreads(remaining)

      if (threadId === thread.id) {
        const nextThreadId = remaining[0]?.id ?? null
        setThreadId(nextThreadId)
        if (!nextThreadId) setMessages([])
      }
    } catch {
      setError('تعذر حذف المحادثة. حاولي مرة أخرى.')
    } finally {
      setDeletingThreadId(null)
    }
  }

  const ask = async (event?: FormEvent, forcedQuestion?: string) => {
    event?.preventDefault()
    const content = (forcedQuestion ?? question).trim()
    if (!content || busy) return

    setBusy(true)
    setError('')
    setQuestion('')

    try {
      let activeThreadId = threadId
      if (!activeThreadId) {
        activeThreadId = await createThread()
      }
      if (!activeThreadId) return

      const optimistic: AssistantMessage = {
        id: `local-${Date.now()}`,
        role: 'user',
        content,
        sources: [],
        created_at: new Date().toISOString(),
      }
      setMessages((current) => [...current, optimistic])

      const response = await apiClient.post<AssistantAnswer>(
        `/assistant/threads/${activeThreadId}/ask`,
        { question: content },
      )
      setMessages((current) => [
        ...current.filter((message) => message.id !== optimistic.id),
        response.data.user_message,
        response.data.assistant_message,
      ])
      await loadThreads()
    } catch {
      setQuestion(content)
      setMessages((current) =>
        current.filter((message) => !message.id.startsWith('local-')),
      )
      setError('تعذر الحصول على إجابة من مساعد وئام.')
    } finally {
      setBusy(false)
    }
  }

  if (!child && !error) {
    return <div className="loading-row"><div className="spinner" /> جاري فتح مساعد وئام...</div>
  }

  if (!child) {
    return <div className="prototype-empty-card"><h2>تعذر فتح المساعد</h2><p>{error}</p><Link className="btn btn-primary" to="/dashboard">الرئيسية</Link></div>
  }

  return (
    <section className="assistant-page">
      <div className="assistant-hero">
        <div>
          <Link className="assistant-back" to={`/children/${child.id}`}>← العودة إلى ملف الطفل</Link>
          <span className="soft-kicker">مساعد وئام</span>
          <h1>مساعد وئام لـ {child.preferred_name || child.first_name}</h1>
          <p>اسألي عن التقارير، الأهداف، الاحتياجات أو الملاحظات المعتمدة. كل إجابة تُظهر مصادرها ولا تستخدم معلومات خارج ملف الطفل.</p>
        </div>
        <span className="assistant-local-badge">✦ يعتمد على بيانات الملف</span>
      </div>

      <div className="assistant-safety-note">
        <strong>مساعد تنسيقي وليس أداة تشخيص</strong>
        <p>يعتمد فقط على البيانات المصرح لك برؤيتها، ويعرض المصدر مع كل إجابة. المسودات غير المعتمدة لا تدخل في الإجابات.</p>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="assistant-shell">
        <aside className="assistant-sidebar">
          <button className="btn btn-primary assistant-new" onClick={() => void createThread()}>＋ محادثة جديدة</button>
          <div className="assistant-thread-title">المحادثات السابقة</div>
          {threads.map((thread) => (
            <div
              key={thread.id}
              className={`assistant-thread-row ${thread.id === threadId ? 'active' : ''}`}
            >
              <button
                className="assistant-thread-item"
                onClick={() => setThreadId(thread.id)}
              >
                <strong>{displayThreadTitle(thread.title)}</strong>
                <small>{new Date(thread.updated_at).toLocaleDateString('ar-SA-u-ca-gregory')}</small>
              </button>
              <button
                type="button"
                className="assistant-thread-delete"
                aria-label={`حذف ${displayThreadTitle(thread.title)}`}
                title="حذف المحادثة"
                disabled={deletingThreadId === thread.id}
                onClick={() => void deleteThread(thread)}
              >
                {deletingThreadId === thread.id ? (
                  '…'
                ) : (
                  <svg
                    viewBox="0 0 24 24"
                    width="15"
                    height="15"
                    aria-hidden="true"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M3 6h18" />
                    <path d="M8 6V4h8v2" />
                    <path d="M19 6l-1 14H6L5 6" />
                    <path d="M10 10v6M14 10v6" />
                  </svg>
                )}
              </button>
            </div>
          ))}
        </aside>

        <main className="assistant-main">
          <div className="assistant-messages">
            {!messages.length && (
              <div className="assistant-welcome">
                <span>✦</span>
                <h2>وش حابة تعرفي من ملف الطفل؟</h2>
                <p>يبحث مساعد وئام داخل المعلومات المعتمدة ويعرض لك إجابة مختصرة مع إمكانية مراجعة مصادرها.</p>
                <div className="assistant-suggestions">
                  {suggestedQuestions.map((item) => (
                    <button key={item} onClick={() => void ask(undefined, item)}>{item}</button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((message) => (
              <div className={`assistant-message ${message.role}`} key={message.id}>
                <div className="assistant-message-avatar">{message.role === 'assistant' ? '✦' : 'أنت'}</div>
                <div className="assistant-message-copy">
                  <div className="assistant-answer-content">
                    {message.role === 'assistant'
                      ? renderAssistantContent(message.content)
                      : <p dir="auto">{message.content}</p>}
                  </div>
                  {message.role === 'assistant' && message.sources.length > 0 && (
                    <details className="assistant-sources">
                      <summary>
                        <span>المصادر المستخدمة ({message.sources.length})</span>
                        <span className="assistant-source-chips">
                          {[...new Set(message.sources.map((source) => source.source_type))].map((type) => (
                            <em key={type}>
                              {type === 'report' ? '📄 تقرير' :
                               type === 'goal' ? '🎯 هدف' :
                               type === 'voice' ? '🎙 ملاحظة' :
                               type === 'profile' ? '👤 الملف' : 'مصدر'}
                            </em>
                          ))}
                        </span>
                      </summary>
                      <div className="assistant-source-list">
                        {message.sources.map((source) => (
                          <article key={`${message.id}-${source.index}`}>
                            <span>[{source.index}]</span>
                            <div className="assistant-source-body">
                              <div className="assistant-source-heading">
                                <h4>{source.title}</h4>
                                <small>
                                  {source.occurred_at
                                    ? new Date(source.occurred_at).toLocaleDateString('ar-SA-u-ca-gregory')
                                    : sourceTypeLabel(source.source_type)}
                                </small>
                              </div>
                              <p className="assistant-source-kind">{sourceTypeLabel(source.source_type)}</p>
                              <details className="assistant-source-excerpt">
                                <summary>عرض مقتطف المصدر</summary>
                                <p dir="auto">{cleanSourceSnippet(source.snippet)}</p>
                              </details>
                            </div>
                          </article>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              </div>
            ))}
            {busy && (
              <div className="assistant-message assistant">
                <div className="assistant-message-avatar">✦</div>
                <div className="assistant-thinking"><span /><span /><span /> يبحث في المصادر المعتمدة...</div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <form className="assistant-composer" onSubmit={(event) => void ask(event)}>
            <textarea
              rows={2}
              dir="auto"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="مثال: ما آخر تقدم في هدف التخاطب؟"
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  event.currentTarget.form?.requestSubmit()
                }
              }}
            />
            <button className="btn btn-primary" disabled={busy || !question.trim()}>إرسال</button>
          </form>
        </main>
      </div>
    </section>
  )
}
