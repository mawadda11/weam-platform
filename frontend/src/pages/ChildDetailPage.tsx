import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { ChildProfile } from '../types'

function displayGender(value?: string | null) {
  if (value === 'female') return 'أنثى'
  if (value === 'male') return 'ذكر'
  if (value === 'other') return 'غير محدد'
  return '—'
}

function Tags({ items, empty = 'لم تُضف بعد' }: { items: string[]; empty?: string }) {
  if (!items.length) return <p className="muted">{empty}</p>
  return <div className="detail-tags">{items.map((item) => <span key={item}>{item}</span>)}</div>
}

export default function ChildDetailPage() {
  const { childId } = useParams()
  const [child, setChild] = useState<ChildProfile | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    apiClient.get<ChildProfile>(`/children/${childId}`).then((response) => setChild(response.data)).catch(() => setError('لم نتمكن من فتح هذا الملف، أو لا تملكين صلاحية الوصول إليه.'))
  }, [childId])

  if (error) return <div className="prototype-empty-card"><h2>تعذر فتح الملف</h2><p>{error}</p><Link className="btn btn-primary" to="/dashboard">العودة للرئيسية</Link></div>
  if (!child) return <div className="loading-row"><div className="spinner" /> جاري تحميل الملف...</div>

  const accessLabel = child.access_role === 'care_provider'
    ? 'مقدم رعاية'
    : child.guardian_type === 'primary' ? 'ولي أمر رئيسي' : 'ولي أمر ثانوي'
  const primary = child.guardian_type === 'primary'
  const canViewReports = primary || child.access_permissions.includes('view_reports')
  const canViewCareTeam = primary || child.access_permissions.includes('view_care_team')
  const canViewGoals = primary || child.access_permissions.includes('view_goals')
  const canViewTimeline = primary || child.access_permissions.includes('view_timeline')

  return (
    <section className="prototype-detail-page">
      <div className="prototype-profile-hero">
        <div className="prototype-profile-avatar"><span>{child.first_name.slice(0, 1)}</span><small>ملف نشط</small></div>
        <div className="prototype-profile-copy"><span className="soft-kicker">ملف الرعاية</span><h1>{child.preferred_name || child.first_name}</h1><p>{child.summary || 'يمكن استكمال هذا الملخص لاحقًا عند وصول التقارير والتحديثات.'}</p></div>
        <div className="prototype-profile-state"><span className="status-pill success">آخر تحديث</span><small>{new Date(child.updated_at).toLocaleDateString('ar-SA')}</small></div>
      </div>

      <div className="profile-shortcuts">
        {canViewReports ? <Link to={`/children/${child.id}/reports`} className="profile-shortcut-link"><span>▤</span><strong>التقارير</strong><small>الملفات وسجل النسخ</small></Link> : <div><span>▤</span><strong>التقارير</strong><small>غير مصرح</small></div>}
        {canViewGoals ? <Link to={`/children/${child.id}/goals`} className="profile-shortcut-link"><span>◎</span><strong>الأهداف</strong><small>الخطة والتقدم</small></Link> : <div><span>◎</span><strong>الأهداف</strong><small>غير مصرح</small></div>}
        {canViewCareTeam ? <Link to={`/children/${child.id}/care-team`} className="profile-shortcut-link"><span>♧</span><strong>فريق الرعاية</strong><small>الفريق والصلاحيات</small></Link> : <div><span>♧</span><strong>فريق الرعاية</strong><small>غير مصرح</small></div>}
        {canViewTimeline ? <Link to={`/children/${child.id}/timeline`} className="profile-shortcut-link"><span>↻</span><strong>الخط الزمني</strong><small>رحلة الطفل كاملة</small></Link> : <div><span>↻</span><strong>الخط الزمني</strong><small>غير مصرح</small></div>}
      </div>

      <div className="prototype-metric-grid">
        <div><span>تاريخ الميلاد</span><strong>{child.birth_date ? new Date(`${child.birth_date}T00:00:00`).toLocaleDateString('ar-SA') : '—'}</strong></div>
        <div><span>الجنس</span><strong>{displayGender(child.gender)}</strong></div>
        <div><span>الخدمات الحالية</span><strong>{child.services.length}</strong></div>
        <div><span>صفة الوصول</span><strong>{accessLabel}</strong></div>
      </div>

      <div className="prototype-detail-grid">
        <article className="prototype-detail-card mint"><div className="detail-card-heading"><span>◌</span><h2>الحالة</h2></div><Tags items={child.conditions} /></article>
        <article className="prototype-detail-card pink"><div className="detail-card-heading"><span>♡</span><h2>الاحتياجات</h2></div><Tags items={child.needs} /></article>
        <article className="prototype-detail-card yellow"><div className="detail-card-heading"><span>✦</span><h2>متطلبات الدعم</h2></div><Tags items={child.support_requirements} /></article>
        <article className="prototype-detail-card lavender"><div className="detail-card-heading"><span>＋</span><h2>الخدمات</h2></div><Tags items={child.services} /></article>
      </div>

      <div className="prototype-next-banner"><div><span className="soft-kicker">Milestone 01</span><h2>الرعاية أصبحت رحلة مترابطة</h2><p>فريق الرعاية والتقارير والأهداف والخط الزمني أصبحت مرتبطة بنفس ملف الطفل وبنفس نظام الصلاحيات.</p></div><span>03</span></div>
    </section>
  )
}
