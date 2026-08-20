import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { CareTeamOverview, ChildGoal, ChildProfile, GoalStatus } from '../types'

const STATUS_LABELS: Record<GoalStatus, string> = {
  new: 'جديد',
  in_progress: 'قيد العمل',
  completed: 'مكتمل',
  paused: 'متوقف مؤقتًا',
}

const EMPTY_FORM = {
  title: '',
  description: '',
  category: '',
  start_date: '',
  target_date: '',
  assigned_to_user_id: '',
}

function formatDate(value?: string | null) {
  if (!value) return '—'
  return new Date(`${value}T00:00:00`).toLocaleDateString('ar-SA-u-ca-gregory', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

export default function GoalsPage() {
  const { childId } = useParams()
  const [child, setChild] = useState<ChildProfile | null>(null)
  const [goals, setGoals] = useState<ChildGoal[]>([])
  const [team, setTeam] = useState<CareTeamOverview | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [updateDrafts, setUpdateDrafts] = useState<Record<string, { note: string; progress: string; status: GoalStatus }>>({})

  const primary = child?.guardian_type === 'primary'
  const canManage = Boolean(primary || child?.access_permissions.includes('manage_goals'))
  const canViewTeam = Boolean(primary || child?.access_permissions.includes('view_care_team'))

  const loadGoals = async () => {
    if (!childId) return
    const response = await apiClient.get<ChildGoal[]>(`/children/${childId}/goals`)
    setGoals(response.data)
  }

  useEffect(() => {
    if (!childId) return
    setError('')
    Promise.all([
      apiClient.get<ChildProfile>(`/children/${childId}`),
      apiClient.get<ChildGoal[]>(`/children/${childId}/goals`),
    ])
      .then(([childResponse, goalsResponse]) => {
        setChild(childResponse.data)
        setGoals(goalsResponse.data)
      })
      .catch(() => setError('تعذر تحميل الأهداف أو لا توجد صلاحية لعرضها.'))
  }, [childId])

  useEffect(() => {
    if (!childId || !canViewTeam) return
    apiClient.get<CareTeamOverview>(`/children/${childId}/care-team`)
      .then((response) => setTeam(response.data))
      .catch(() => setTeam(null))
  }, [childId, canViewTeam])

  const activeMembers = useMemo(
    () => team?.members.filter((item) => item.access_status === 'active') ?? [],
    [team],
  )

  const createGoal = async (event: FormEvent) => {
    event.preventDefault()
    if (!childId || !form.title.trim()) return
    setBusy(true)
    setError('')
    setSuccess('')
    try {
      await apiClient.post(`/children/${childId}/goals`, {
        title: form.title,
        description: form.description || null,
        category: form.category || null,
        start_date: form.start_date || null,
        target_date: form.target_date || null,
        assigned_to_user_id: form.assigned_to_user_id || null,
      })
      setForm(EMPTY_FORM)
      setShowForm(false)
      setSuccess('تم إنشاء الهدف وربطه بملف الرعاية.')
      await loadGoals()
    } catch {
      setError('تعذر إنشاء الهدف. تأكدي من التواريخ ومسؤول الهدف.')
    } finally {
      setBusy(false)
    }
  }

  const draftFor = (goal: ChildGoal) => updateDrafts[goal.id] ?? {
    note: '',
    progress: String(goal.progress_percent),
    status: goal.status,
  }

  const updateDraft = (goal: ChildGoal, values: Partial<{ note: string; progress: string; status: GoalStatus }>) => {
    setUpdateDrafts((current) => ({
      ...current,
      [goal.id]: { ...draftFor(goal), ...values },
    }))
  }

  const saveProgress = async (goal: ChildGoal) => {
    const draft = draftFor(goal)
    setBusy(true)
    setError('')
    setSuccess('')
    try {
      await apiClient.post(`/goals/${goal.id}/updates`, {
        note: draft.note || null,
        progress_percent: Number(draft.progress),
        status: draft.status,
      })
      setUpdateDrafts((current) => {
        const next = { ...current }
        delete next[goal.id]
        return next
      })
      setSuccess(`تم تحديث هدف "${goal.title}".`)
      await loadGoals()
    } catch {
      setError('تعذر حفظ تحديث الهدف.')
    } finally {
      setBusy(false)
    }
  }

  if (error && !child) return <div className="prototype-empty-card"><h2>تعذر فتح الأهداف</h2><p>{error}</p><Link className="btn btn-primary" to="/dashboard">العودة للرئيسية</Link></div>
  if (!child) return <div className="loading-row"><div className="spinner" /> جاري تحميل الأهداف...</div>

  return (
    <section className="m1-feature-page">
      <div className="m1-feature-hero goals-hero">
        <div>
          <div className="m1-breadcrumb-row">
            <Link className="m1-back-link" to={`/children/${child.id}`}>← العودة لملف الطفل</Link>
          </div>
          <span className="soft-kicker m1-feature-kicker">الأهداف المشتركة</span>
          <h1>أهداف {child.preferred_name || child.first_name}</h1>
          <p>كل هدف له مسؤول واضح، تاريخ مستهدف، تقدم محفوظ، وتحديثات مرتبطة باسم صاحبها وتاريخها.</p>
        </div>
        <div className="m1-hero-actions">
          <div className="m1-count-card"><strong>{goals.length}</strong><span>هدف</span></div>
          {canManage && <button className="btn btn-primary" onClick={() => setShowForm((value) => !value)}>＋ هدف جديد</button>}
        </div>
      </div>

      {success && <div className="alert alert-success">{success}</div>}
      {error && <div className="alert alert-error">{error}</div>}

      {showForm && canManage && (
        <form className="m1-form-card" onSubmit={createGoal}>
          <div className="m1-section-heading"><span>◎</span><div><h2>إضافة هدف</h2><p>اكتبي الهدف بشكل واضح وقابل للمتابعة.</p></div></div>
          <div className="form-grid two">
            <label className="field"><span>عنوان الهدف *</span><input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="مثال: استخدام جمل من 4 كلمات" required /></label>
            <label className="field"><span>التصنيف</span><input value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} placeholder="تخاطب، سلوك، علاج وظيفي..." /></label>
          </div>
          <label className="field"><span>وصف الهدف</span><textarea rows={3} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="ما النتيجة التي نريد الوصول إليها؟" /></label>
          <div className="form-grid two">
            <label className="field"><span>تاريخ البداية</span><input type="date" value={form.start_date} onChange={(event) => setForm({ ...form, start_date: event.target.value })} /></label>
            <label className="field"><span>التاريخ المستهدف</span><input type="date" value={form.target_date} onChange={(event) => setForm({ ...form, target_date: event.target.value })} /></label>
          </div>
          {canViewTeam && (
            <label className="field"><span>مسؤول الهدف</span><select className="weam-select" value={form.assigned_to_user_id} onChange={(event) => setForm({ ...form, assigned_to_user_id: event.target.value })}><option value="">بدون تعيين</option>{activeMembers.map((member) => <option key={member.user_id} value={member.user_id}>{member.full_name} — {member.role_label || member.account_role}</option>)}</select></label>
          )}
          <div className="m1-form-actions"><button type="button" className="btn btn-white" onClick={() => setShowForm(false)}>إلغاء</button><button className="btn btn-primary" disabled={busy}>{busy ? 'جارٍ الحفظ...' : 'حفظ الهدف'}</button></div>
        </form>
      )}

      {!goals.length ? (
        <div className="prototype-empty-card"><span>◎</span><h2>لا توجد أهداف بعد</h2><p>ابدؤوا بهدف واحد واضح، ثم حدثوا التقدم بشكل مستمر ليبقى الفريق على نفس الصورة.</p>{canManage && <button className="btn btn-primary" onClick={() => setShowForm(true)}>إنشاء أول هدف</button>}</div>
      ) : (
        <div className="goals-grid">
          {goals.map((goal) => {
            const draft = draftFor(goal)
            return (
              <article key={goal.id} className="goal-card">
                <div className="goal-card-top">
                  <div><div className="goal-badges">{goal.category && <span>{goal.category}</span>}<span className={`goal-status ${goal.status}`}>{STATUS_LABELS[goal.status]}</span></div><h2>{goal.title}</h2><p>{goal.description || 'لا يوجد وصف إضافي.'}</p></div>
                  <strong className="goal-percent">{goal.progress_percent}%</strong>
                </div>
                <div className="goal-progress-track"><span style={{ width: `${goal.progress_percent}%` }} /></div>
                <div className="goal-meta">
                  <div><span>مسؤول الهدف</span><strong>{goal.assigned_to_name || 'غير معين'}</strong></div>
                  <div><span>البداية</span><strong>{formatDate(goal.start_date)}</strong></div>
                  <div><span>المستهدف</span><strong>{formatDate(goal.target_date)}</strong></div>
                </div>

                {canManage && (
                  <div className="goal-update-box">
                    <h3>تحديث التقدم</h3>
                    <div className="goal-update-controls">
                      <label><span>النسبة</span><input type="number" min="0" max="100" value={draft.progress} onChange={(event) => updateDraft(goal, { progress: event.target.value })} /></label>
                      <label><span>الحالة</span><select className="weam-select" value={draft.status} onChange={(event) => updateDraft(goal, { status: event.target.value as GoalStatus })}><option value="new">جديد</option><option value="in_progress">قيد العمل</option><option value="completed">مكتمل</option><option value="paused">متوقف مؤقتًا</option></select></label>
                    </div>
                    <label className="field"><span>ملاحظة</span><input value={draft.note} onChange={(event) => updateDraft(goal, { note: event.target.value })} placeholder="ما الذي تغيّر منذ آخر متابعة؟" /></label>
                    <button className="btn btn-primary btn-small" onClick={() => saveProgress(goal)} disabled={busy}>حفظ التحديث</button>
                  </div>
                )}

                <div className="goal-history">
                  <div className="m1-subheading"><h3>آخر التحديثات</h3><span>{goal.updates.length}</span></div>
                  {goal.updates.length ? goal.updates.slice(0, 4).map((item) => (
                    <div key={item.id} className="goal-history-item">
                      <span className="goal-history-dot" />
                      <div><strong>{item.actor_name}</strong><p>{item.note || `التقدم ${item.progress_percent}% — ${STATUS_LABELS[item.status]}`}</p><small>{new Date(item.created_at).toLocaleString('ar-SA-u-ca-gregory')}</small></div>
                    </div>
                  )) : <p className="muted">لا توجد تحديثات تقدم بعد.</p>}
                </div>
              </article>
            )
          })}
        </div>
      )}

      <div className="m1-footer-link"><Link className="btn btn-white" to={`/children/${child.id}/timeline`}>عرض رحلة الطفل في الخط الزمني ←</Link></div>
    </section>
  )
}
