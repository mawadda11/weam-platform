import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { ChildProfile, FollowUpItem } from '../types'
import '../styles/m3-followups-notifications.css'

const STATUS_LABELS = {
  upcoming: 'قادمة',
  today: 'اليوم',
  overdue: 'متأخرة',
  completed: 'مكتملة',
}

function formatDate(value?: string | null) {
  if (!value) return 'بدون موعد محدد'
  return new Date(`${value}T00:00:00`).toLocaleDateString('ar-SA-u-ca-gregory')
}

export default function FollowUpsPage() {
  const { childId } = useParams()
  const [child, setChild] = useState<ChildProfile | null>(null)
  const [items, setItems] = useState<FollowUpItem[]>([])
  const [filter, setFilter] = useState<'all' | FollowUpItem['display_status']>('all')
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [title, setTitle] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState('')
  const [dateDrafts, setDateDrafts] = useState<Record<string, string>>({})
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  const load = async () => {
    if (!childId) return
    const childResponse = await apiClient.get<ChildProfile>(`/children/${childId}`)
    const profile = childResponse.data
    setChild(profile)

    const canManageProfile =
      profile.guardian_type === 'primary' ||
      profile.access_permissions.includes('manage_goals')

    if (canManageProfile) {
      try {
        await apiClient.post(`/children/${childId}/follow-ups/sync-approved-analyses`)
      } catch {
        // Backfill is best-effort; listing manual follow-ups should still work.
      }
    }

    const followUpsResponse = await apiClient.get<FollowUpItem[]>(
      `/children/${childId}/follow-ups?status=all`,
    )
    setItems(followUpsResponse.data)
    setDateDrafts((current) => {
      const next = { ...current }
      followUpsResponse.data.forEach((item) => {
        if (item.due_date && !(item.id in next)) next[item.id] = item.due_date
      })
      return next
    })
  }

  useEffect(() => {
    setLoading(true)
    setError('')
    void load()
      .catch(() => setError('تعذر تحميل المتابعات أو لا توجد صلاحية للوصول إليها.'))
      .finally(() => setLoading(false))
  }, [childId])

  const canManage = Boolean(
    child &&
    (
      child.guardian_type === 'primary' ||
      child.access_permissions.includes('manage_goals')
    )
  )

  const counts = useMemo(() => ({
    today: items.filter((item) => item.display_status === 'today').length,
    upcoming: items.filter((item) => item.display_status === 'upcoming' && item.status === 'open').length,
    overdue: items.filter((item) => item.display_status === 'overdue').length,
    completed: items.filter((item) => item.display_status === 'completed').length,
  }), [items])

  const autoCreated = useMemo(
    () => items.filter((item) => item.source_type === 'report_ai').length,
    [items],
  )

  const needsDate = useMemo(
    () => items.filter((item) => item.status === 'open' && !item.due_date).length,
    [items],
  )

  const visible = filter === 'all'
    ? items
    : items.filter((item) => item.display_status === filter)

  const createManual = async (event: FormEvent) => {
    event.preventDefault()
    if (!childId || !title.trim() || busy) return
    setBusy('create')
    setError('')
    setNotice('')
    try {
      await apiClient.post(`/children/${childId}/follow-ups`, {
        title: title.trim(),
        due_date: dueDate || null,
        note: note.trim() || null,
      })
      setTitle('')
      setDueDate('')
      setNote('')
      setShowCreate(false)
      setNotice('تمت إضافة المتابعة.')
      await load()
      window.dispatchEvent(new Event('weam:notifications-changed'))
    } catch {
      setError('تعذر إضافة المتابعة.')
    } finally {
      setBusy('')
    }
  }

  const saveDate = async (item: FollowUpItem) => {
    const value = dateDrafts[item.id]
    if (!value || busy) return
    setBusy(`date:${item.id}`)
    setError('')
    try {
      await apiClient.patch(`/follow-ups/${item.id}`, { due_date: value })
      setNotice('تم حفظ موعد المتابعة.')
      await load()
      window.dispatchEvent(new Event('weam:notifications-changed'))
    } catch {
      setError('تعذر حفظ موعد المتابعة.')
    } finally {
      setBusy('')
    }
  }

  const complete = async (item: FollowUpItem) => {
    if (busy) return
    setBusy(item.id)
    setError('')
    try {
      await apiClient.post(`/follow-ups/${item.id}/complete`)
      await load()
      window.dispatchEvent(new Event('weam:notifications-changed'))
    } catch {
      setError('تعذر تحديث حالة المتابعة.')
    } finally {
      setBusy('')
    }
  }

  const reopen = async (item: FollowUpItem) => {
    if (busy) return
    setBusy(item.id)
    setError('')
    try {
      await apiClient.post(`/follow-ups/${item.id}/reopen`)
      await load()
      window.dispatchEvent(new Event('weam:notifications-changed'))
    } catch {
      setError('تعذر إعادة فتح المتابعة.')
    } finally {
      setBusy('')
    }
  }

  const remove = async (item: FollowUpItem) => {
    if (busy || !window.confirm(`حذف متابعة «${item.title}»؟`)) return
    setBusy(item.id)
    try {
      await apiClient.delete(`/follow-ups/${item.id}`)
      await load()
      window.dispatchEvent(new Event('weam:notifications-changed'))
    } catch {
      setError('تعذر حذف المتابعة.')
    } finally {
      setBusy('')
    }
  }

  if (loading && !child) {
    return <div className="loading-row"><div className="spinner" /> جاري تحميل المتابعات...</div>
  }

  return (
    <section className="m3-page">
      <div className="m3-hero">
        <div>
          <Link className="m3-back" to={child ? `/children/${child.id}` : '/dashboard'}>← العودة إلى ملف الطفل</Link>
          <span className="soft-kicker">المتابعات</span>
          <h1>كل موعد مهم في مكان واحد</h1>
          <p>
            ينظم وئام مواعيد المتابعة الواردة في تقارير الرعاية، ويذكّرك بها في الوقت المناسب.
            ويمكنك إضافة أي متابعة أخرى بنفسك متى احتجت.
          </p>
        </div>
        {canManage && (
          <button className="btn btn-primary" onClick={() => setShowCreate((value) => !value)}>
            {showCreate ? 'إغلاق النموذج' : '＋ إضافة متابعة'}
          </button>
        )}
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}

      <div className="m3-metrics">
        <button onClick={() => setFilter('today')}><span>اليوم</span><strong>{counts.today}</strong></button>
        <button onClick={() => setFilter('upcoming')}><span>قادمة</span><strong>{counts.upcoming}</strong></button>
        <button className={counts.overdue ? 'danger' : ''} onClick={() => setFilter('overdue')}><span>متأخرة</span><strong>{counts.overdue}</strong></button>
        <button onClick={() => setFilter('completed')}><span>مكتملة</span><strong>{counts.completed}</strong></button>
      </div>

      {autoCreated > 0 && (
        <div className="m3-auto-banner">
          <span className="m3-auto-icon">✓</span>
          <div>
            <strong>أضاف وئام {autoCreated} متابعة من تقارير الرعاية</strong>
            <p>
              {needsDate > 0
                ? `${needsDate} منها بدون موعد محدد. يمكنك تحديد الموعد إذا كان معروفًا لديك.`
                : 'كل المواعيد الواضحة أصبحت منظمة وجاهزة للمتابعة.'}
            </p>
          </div>
        </div>
      )}

      {showCreate && canManage && (
        <form className="m3-create-card" onSubmit={(event) => void createManual(event)}>
          <div>
            <span className="soft-kicker">متابعة جديدة</span>
            <h2>أضيفي موعدًا أو تذكيرًا</h2>
          </div>
          <label>
            عنوان المتابعة
            <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="مثال: مراجعة السمعيات" required />
          </label>
          <label>
            التاريخ
            <input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
          </label>
          <label className="wide">
            ملاحظة
            <textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="تفاصيل مختصرة للفريق..." />
          </label>
          <div className="m3-form-actions wide">
            <button className="btn btn-primary" disabled={busy === 'create'}>{busy === 'create' ? 'جارٍ الحفظ...' : 'حفظ المتابعة'}</button>
          </div>
        </form>
      )}

      <div className="m3-toolbar">
        <div>
          <h2>قائمة المتابعات</h2>
          <p>{items.length} متابعة في الملف</p>
        </div>
        <div className="m3-filter-tabs">
          <button className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>الكل</button>
          <button className={filter === 'today' ? 'active' : ''} onClick={() => setFilter('today')}>اليوم</button>
          <button className={filter === 'upcoming' ? 'active' : ''} onClick={() => setFilter('upcoming')}>قادمة</button>
          <button className={filter === 'overdue' ? 'active' : ''} onClick={() => setFilter('overdue')}>متأخرة</button>
          <button className={filter === 'completed' ? 'active' : ''} onClick={() => setFilter('completed')}>مكتملة</button>
        </div>
      </div>

      {!visible.length ? (
        <div className="prototype-empty-card">
          <span>✓</span>
          <h2>لا توجد متابعات هنا</h2>
          <p>ستظهر هنا المواعيد القادمة، ويمكنك إضافة متابعة جديدة في أي وقت.</p>
        </div>
      ) : (
        <div className="m3-followup-list">
          {visible.map((item) => {
            const missingDate = item.status === 'open' && !item.due_date
            return (
              <article key={item.id} className={`m3-followup-card ${item.display_status} ${missingDate ? 'needs-date' : ''}`}>
                <div className="m3-followup-date">
                  <span>{item.due_date ? new Date(`${item.due_date}T00:00:00`).toLocaleDateString('ar-SA-u-ca-gregory', { day: 'numeric' }) : '؟'}</span>
                  <small>{item.due_date ? new Date(`${item.due_date}T00:00:00`).toLocaleDateString('ar-SA-u-ca-gregory', { month: 'short' }) : 'يحتاج موعد'}</small>
                </div>
                <div className="m3-followup-body">
                  <div className="m3-followup-head">
                    <div>
                      <span className={`m3-status ${missingDate ? 'needs-date' : item.display_status}`}>
                        {missingDate ? 'يحتاج تحديد موعد' : STATUS_LABELS[item.display_status]}
                      </span>
                      {item.source_type === 'report_ai' && <span className="m3-source-chip">من تقرير الرعاية</span>}
                    </div>
                    <small>{formatDate(item.due_date)}</small>
                  </div>
                  <h3>{item.title}</h3>
                  {item.note && item.note.trim() !== item.title.trim() && <p>{item.note}</p>}

                  {missingDate && canManage && (
                    <div className="m3-date-confirm">
                      <div>
                        <strong>لم يُذكر موعد محدد لهذه المتابعة</strong>
                        <small>يمكنك تحديد موعد الآن، أو ترك المتابعة بدون تاريخ.</small>
                      </div>
                      <input
                        type="date"
                        value={dateDrafts[item.id] || ''}
                        onChange={(event) => setDateDrafts({ ...dateDrafts, [item.id]: event.target.value })}
                        aria-label="موعد المتابعة"
                      />
                      <button
                        className="btn btn-white btn-small"
                        disabled={!dateDrafts[item.id] || busy === `date:${item.id}`}
                        onClick={() => void saveDate(item)}
                      >
                        تأكيد الموعد
                      </button>
                    </div>
                  )}

                  {canManage && (
                    <div className="m3-followup-actions">
                      {item.status === 'completed' ? (
                        <button className="btn btn-white btn-small" disabled={busy === item.id} onClick={() => void reopen(item)}>إعادة فتح</button>
                      ) : (
                        <button className="btn btn-primary btn-small" disabled={busy === item.id} onClick={() => void complete(item)}>✓ تم الإنجاز</button>
                      )}
                      <button className="m3-delete-button" disabled={busy === item.id} onClick={() => void remove(item)} aria-label="حذف المتابعة">
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                          <path d="M3 6h18" /><path d="M8 6V4h8v2" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 10v6M14 10v6" />
                        </svg>
                      </button>
                    </div>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}
