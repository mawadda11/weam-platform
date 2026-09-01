import { useEffect, useMemo, useState } from 'react'
import { apiClient } from '../api/client'
import type { AdminAuditItem, AdminCenter, AdminSummary, AdminUser } from '../types'
import '../styles/admin-dashboard.css'

const roleLabels: Record<string, string> = {
  guardian: 'ولي أمر',
  care_provider: 'مقدم رعاية',
  center: 'حساب مركز',
  admin: 'إدارة',
}

const verificationLabels: Record<string, string> = {
  verified: 'موثّق',
  unverified: 'قيد المراجعة',
  rejected: 'مرفوض',
}

const normalize = (value: string | null | undefined) => (value || '').trim().toLocaleLowerCase()

const STALE_REVIEW_DAYS = 120

function reviewAge(lastReviewedAt?: string | null): { label: string; stale: boolean } {
  if (!lastReviewedAt) return { label: 'لم تتم مراجعته بعد', stale: true }
  const days = Math.floor((Date.now() - new Date(lastReviewedAt).getTime()) / 86_400_000)
  const label = days === 0 ? 'آخر مراجعة اليوم' : `آخر مراجعة قبل ${days} يومًا`
  return { label, stale: days > STALE_REVIEW_DAYS }
}

export default function AdminDashboardPage() {
  const [summary, setSummary] = useState<AdminSummary | null>(null)
  const [users, setUsers] = useState<AdminUser[]>([])
  const [centers, setCenters] = useState<AdminCenter[]>([])
  const [audit, setAudit] = useState<AdminAuditItem[]>([])
  const [tab, setTab] = useState<'overview' | 'users' | 'centers' | 'audit'>('overview')
  const [userQuery, setUserQuery] = useState('')
  const [userRole, setUserRole] = useState('')
  const [userStatus, setUserStatus] = useState('')
  const [centerQuery, setCenterQuery] = useState('')
  const [centerStatus, setCenterStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState('')
  const [error, setError] = useState('')

  const load = async () => {
    const [summaryResponse, usersResponse, centersResponse, auditResponse] = await Promise.all([
      apiClient.get<AdminSummary>('/admin/summary'),
      apiClient.get<AdminUser[]>('/admin/users'),
      apiClient.get<AdminCenter[]>('/admin/centers'),
      apiClient.get<AdminAuditItem[]>('/admin/audit'),
    ])
    setSummary(summaryResponse.data)
    setUsers(usersResponse.data)
    setCenters(centersResponse.data)
    setAudit(auditResponse.data)
  }

  useEffect(() => {
    load().catch(() => setError('تعذر فتح لوحة الإدارة أو لا توجد لديك صلاحية إدارية.')).finally(() => setLoading(false))
  }, [])

  const filteredUsers = useMemo(() => {
    const query = normalize(userQuery)
    return users.filter((item) => {
      const matchesQuery = !query || normalize(item.full_name).includes(query) || normalize(item.email).includes(query)
      return matchesQuery && (!userRole || item.role === userRole) && (!userStatus || item.verification_status === userStatus)
    })
  }, [users, userQuery, userRole, userStatus])

  const filteredCenters = useMemo(() => {
    const query = normalize(centerQuery)
    return centers.filter((item) => {
      const matchesQuery = !query
        || normalize(item.name).includes(query)
        || normalize(item.city).includes(query)
        || normalize(item.account_email).includes(query)
      return matchesQuery && (!centerStatus || item.verification_status === centerStatus)
    })
  }, [centers, centerQuery, centerStatus])

  const reviewUser = async (item: AdminUser, values: Record<string, unknown>) => {
    setBusyId(item.id)
    setError('')
    try {
      await apiClient.patch<AdminUser>(`/admin/users/${item.id}`, values)
      await load()
    } catch {
      setError('تعذر تحديث الحساب.')
    } finally {
      setBusyId('')
    }
  }

  const reviewCenter = async (item: AdminCenter, values: Record<string, unknown>) => {
    setBusyId(item.id)
    setError('')
    try {
      await apiClient.patch<AdminCenter>(`/admin/centers/${item.id}`, values)
      await load()
    } catch {
      setError('تعذر تحديث المركز.')
    } finally {
      setBusyId('')
    }
  }

  if (loading) return <div className="loading-row"><div className="spinner" /> جاري تحميل لوحة الإدارة...</div>
  if (!summary) return <div className="prototype-empty-card"><span>!</span><h2>تعذر فتح لوحة الإدارة</h2><p>{error}</p></div>

  return (
    <section className="admin-dashboard-page">
      <div className="admin-hero">
        <div><span className="soft-kicker">إدارة وئام</span><h1>نظرة تشغيلية آمنة</h1><p>إدارة الحسابات والمراكز والاعتمادات دون عرض التقارير أو المعلومات الطبية للأطفال.</p></div>
        <span>▦</span>
      </div>
      {error && <div className="alert alert-error">{error}</div>}

      <nav className="admin-tabs" aria-label="أقسام لوحة الإدارة">
        <button className={tab === 'overview' ? 'active' : ''} onClick={() => setTab('overview')}>نظرة عامة</button>
        <button className={tab === 'users' ? 'active' : ''} onClick={() => setTab('users')}>الحسابات <b>{summary.pending_accounts || ''}</b></button>
        <button className={tab === 'centers' ? 'active' : ''} onClick={() => setTab('centers')}>المراكز <b>{summary.pending_centers || ''}</b></button>
        <button className={tab === 'audit' ? 'active' : ''} onClick={() => setTab('audit')}>سجل الإدارة</button>
      </nav>

      {tab === 'overview' && (
        <div className="admin-stat-grid">
          <article><span>إجمالي الحسابات</span><strong>{summary.users_total}</strong><small>{summary.users_active} حسابات فعالة</small></article>
          <article><span>بانتظار مراجعة الحساب</span><strong>{summary.pending_accounts}</strong><small>مقدمو رعاية ومراكز</small></article>
          <article><span>المراكز</span><strong>{summary.centers_total}</strong><small>{summary.centers_active} مراكز فعالة</small></article>
          <article><span>بانتظار اعتماد المركز</span><strong>{summary.pending_centers}</strong><small>لا تظهر في الدليل قبل الاعتماد</small></article>
          <article><span>ملفات الأطفال</span><strong>{summary.child_profiles_total}</strong><small>إحصاء إجمالي فقط دون محتوى طبي</small></article>
        </div>
      )}

      {tab === 'users' && (
        <div className="admin-panel">
          <div className="admin-panel-head"><div><span className="soft-kicker">الحسابات</span><h2>التحقق وحالة الوصول</h2></div><small>{filteredUsers.length} من {users.length} حسابًا</small></div>
          <div className="admin-filter-bar">
            <label className="admin-search-field">بحث عن حساب<input value={userQuery} onChange={(event) => setUserQuery(event.target.value)} placeholder="الاسم أو البريد الإلكتروني" /></label>
            <label>نوع الحساب<select value={userRole} onChange={(event) => setUserRole(event.target.value)}><option value="">كل الأنواع</option><option value="guardian">ولي أمر</option><option value="care_provider">مقدم رعاية</option><option value="center">حساب مركز</option><option value="admin">إدارة</option></select></label>
            <label>حالة التحقق<select value={userStatus} onChange={(event) => setUserStatus(event.target.value)}><option value="">كل الحالات</option><option value="unverified">قيد المراجعة</option><option value="verified">موثّق</option><option value="rejected">مرفوض</option></select></label>
          </div>
          <div className="admin-table-wrap">
            <table>
              <thead><tr><th>الحساب</th><th>النوع</th><th>التحقق</th><th>الحالة</th><th>الإجراء</th></tr></thead>
              <tbody>
                {!filteredUsers.length && <tr><td className="admin-empty-row" colSpan={5}>لا توجد حسابات مطابقة لعوامل البحث.</td></tr>}
                {filteredUsers.map((item) => (
                  <tr key={item.id}>
                    <td><strong>{item.full_name}</strong><small>{item.email}</small></td>
                    <td>{roleLabels[item.role]}</td>
                    <td><span className={`admin-state ${item.verification_status}`}>{verificationLabels[item.verification_status]}</span></td>
                    <td>{item.is_active ? 'فعّال' : 'موقوف'}</td>
                    <td><div className="admin-actions">
                      {item.verification_status !== 'verified' && <button disabled={busyId === item.id} onClick={() => void reviewUser(item, { verification_status: 'verified', verification_note: 'تمت مراجعة الحساب واعتماده.' })}>اعتماد</button>}
                      {item.verification_status !== 'rejected' && item.role !== 'admin' && <button className="danger" disabled={busyId === item.id} onClick={() => void reviewUser(item, { verification_status: 'rejected', verification_note: 'يرجى تحديث بيانات الحساب والتواصل مع إدارة وئام.' })}>رفض</button>}
                      {item.role !== 'admin' && <button className="muted" disabled={busyId === item.id} onClick={() => void reviewUser(item, { is_active: !item.is_active })}>{item.is_active ? 'إيقاف' : 'تفعيل'}</button>}
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'centers' && (
        <div className="admin-panel">
          <div className="admin-panel-head"><div><span className="soft-kicker">المراكز</span><h2>اعتماد الدليل</h2></div><small>{filteredCenters.length} من {centers.length} مركزًا</small></div>
          <p className="admin-panel-note">
            مراجعة المصدر شيء، واعتماد وئام الرسمي شيء آخر: تسجيل مصادر مركز ومتى رُوجعت لا يعني أنه معتمد —
            الاعتماد قرار منفصل بعد التأكد من صحة البيانات.
          </p>
          <div className="admin-filter-bar centers">
            <label className="admin-search-field">بحث عن مركز<input value={centerQuery} onChange={(event) => setCenterQuery(event.target.value)} placeholder="اسم المركز أو المدينة أو البريد" /></label>
            <label>حالة التحقق<select value={centerStatus} onChange={(event) => setCenterStatus(event.target.value)}><option value="">كل الحالات</option><option value="unverified">قيد المراجعة</option><option value="verified">موثّق</option><option value="rejected">مرفوض</option></select></label>
          </div>
          <div className="admin-table-wrap">
            <table>
              <thead><tr><th>المركز</th><th>المدينة</th><th>حساب الإدارة</th><th>مصدر البيانات</th><th>التحقق</th><th>الإجراء</th></tr></thead>
              <tbody>
                {!filteredCenters.length && <tr><td className="admin-empty-row" colSpan={6}>لا توجد مراكز مطابقة لعوامل البحث.</td></tr>}
                {filteredCenters.map((item) => {
                  const age = reviewAge(item.last_reviewed_at)
                  const isPublicResearch = item.source_type === 'public_research'
                  return (
                    <tr key={item.id}>
                      <td><strong>{item.name}</strong><small>{item.is_active ? 'فعّال' : 'موقوف'}</small></td>
                      <td>{item.city}</td>
                      <td>{item.account_email || 'بيانات تجريبية'}</td>
                      <td>
                        <div className="admin-source-cell">
                          <span className={`admin-source-badge ${item.source_type}`}>
                            {isPublicResearch ? 'مصادر عامة' : 'بيانات تجريبية'}
                          </span>
                          {isPublicResearch && (
                            <>
                              <small className={age.stale ? 'stale' : ''}>{age.label}</small>
                              {item.data_confidence && <small>موثوقية البيانات: {item.data_confidence === 'high' ? 'عالية' : item.data_confidence}</small>}
                              {item.source_urls[0] && (
                                <a href={item.source_urls[0]} target="_blank" rel="noreferrer noopener">عرض المصدر ↗</a>
                              )}
                            </>
                          )}
                        </div>
                      </td>
                      <td><span className={`admin-state ${item.verification_status}`}>{verificationLabels[item.verification_status]}</span></td>
                      <td><div className="admin-actions">
                        {isPublicResearch && (
                          <button className="muted" disabled={busyId === item.id} onClick={() => void reviewCenter(item, { mark_reviewed: true })}>تحديد كمُراجَع اليوم</button>
                        )}
                        {item.verification_status !== 'verified' && <button disabled={busyId === item.id} onClick={() => void reviewCenter(item, { verification_status: 'verified', verification_note: 'تمت مراجعة بيانات المركز واعتماده.' })}>اعتماد</button>}
                        {item.verification_status !== 'rejected' && <button className="danger" disabled={busyId === item.id} onClick={() => void reviewCenter(item, { verification_status: 'rejected', verification_note: 'تحتاج بيانات المركز إلى تحديث قبل الاعتماد.' })}>رفض</button>}
                        <button className="muted" disabled={busyId === item.id} onClick={() => void reviewCenter(item, { is_active: !item.is_active })}>{item.is_active ? 'إيقاف' : 'تفعيل'}</button>
                      </div></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'audit' && (
        <div className="admin-panel">
          <div className="admin-panel-head"><div><span className="soft-kicker">سجل الإدارة</span><h2>القرارات الإدارية</h2></div><small>لا يحتوي بيانات طبية</small></div>
          {!audit.length
            ? <div className="provider-inline-empty">لا توجد إجراءات إدارية مسجلة بعد.</div>
            : <div className="admin-audit-list">{audit.map((item) => <article key={item.id}><span>{item.action === 'center_reviewed' ? '⌂' : '✓'}</span><div><strong>{item.action === 'center_reviewed' ? 'مراجعة مركز' : 'مراجعة حساب'}</strong><p>بواسطة {item.actor_name}</p></div><time>{new Date(item.created_at).toLocaleString('ar-SA-u-ca-gregory')}</time></article>)}</div>}
        </div>
      )}
    </section>
  )
}
