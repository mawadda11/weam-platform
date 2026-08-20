import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiClient } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import type { ChildProfile } from '../types'

export default function DashboardPage() {
  const { user } = useAuth()
  const [children, setChildren] = useState<ChildProfile[]>([])
  const [selectedChildId, setSelectedChildId] = useState<string>('')
  const canAccessChildren = user?.role === 'guardian' || user?.role === 'care_provider'
  const [loading, setLoading] = useState(canAccessChildren)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!canAccessChildren) return
    setLoading(true)
    apiClient.get<ChildProfile[]>('/children')
      .then((response) => {
        setChildren(response.data)
        setSelectedChildId((current) => current || response.data[0]?.id || '')
      })
      .catch(() => setError('تعذر تحميل ملفات الأطفال.'))
      .finally(() => setLoading(false))
  }, [canAccessChildren])

  const selectedChild = useMemo(() => children.find((child) => child.id === selectedChildId) ?? children[0], [children, selectedChildId])

  if (!canAccessChildren) {
    return (
      <section className="provider-dashboard">
        <div className="soft-dashboard-banner">
          <div><span className="soft-kicker">مرحبًا {user?.full_name}</span><h1>حسابك جاهز كبداية ✨</h1><p>سيتم تفعيل لوحة هذا النوع من الحسابات في المراحل القادمة.</p></div>
          {user?.verification_status === 'unverified' && <span className="status-pill warning">غير موثّق</span>}
        </div>
      </section>
    )
  }

  if (loading) return <div className="loading-row"><div className="spinner" /> جاري تحميل الملفات...</div>

  if (user?.role === 'care_provider') {
    return (
      <section className="provider-dashboard">
        {error && <div className="alert alert-error">{error}</div>}
        <div className="soft-dashboard-banner">
          <div><span className="soft-kicker">مرحبًا {user.full_name}</span><h1>فريق الرعاية في مساحة واحدة</h1><p>تظهر هنا فقط ملفات الأطفال التي قُبلت دعوتك للوصول إليها وضمن الصلاحيات المحددة لك.</p></div>
          <Link className="btn btn-primary" to="/invitations">عرض الدعوات</Link>
        </div>
        {children.length ? (
          <div className="provider-child-grid">
            {children.map((child) => (
              <Link key={child.id} to={`/children/${child.id}`} className="provider-child-card">
                <span className="provider-child-avatar">{child.first_name.slice(0, 1)}</span>
                <div><small>ملف مصرح</small><h2>{child.preferred_name || child.first_name}</h2><p>{child.needs[0] || child.services[0] || 'ملف رعاية'}</p></div>
                <span>←</span>
              </Link>
            ))}
          </div>
        ) : (
          <div className="prototype-empty-card"><span>✉</span><h2>لا توجد ملفات مصرح بها بعد</h2><p>افتحي صفحة الدعوات واقبلي دعوة ولي الأمر أولًا.</p><Link className="btn btn-primary" to="/invitations">عرض الدعوات</Link></div>
        )}
      </section>
    )
  }

  if (!children.length) {
    return (
      <section className="guardian-dashboard">
        <div className="soft-dashboard-banner">
          <div><span className="soft-kicker">مرحبًا {user?.full_name} 💛</span><h1>نبدأ أول رحلة مع وئام</h1><p>أنشئي ملف الطفل، وبعدها نربط فريق الرعاية والتقارير والأهداف.</p></div>
          <Link className="btn btn-primary" to="/children/new">＋ إضافة طفل</Link>
        </div>
        <div className="prototype-empty-card"><span>🌱</span><h2>لا يوجد ملف طفل بعد</h2><p>سنطلب فقط المعلومات الأساسية الآن، ويمكن إكمال الباقي تدريجيًا.</p><Link className="btn btn-primary" to="/children/new">إنشاء ملف طفل</Link></div>
      </section>
    )
  }

  return (
    <section className="guardian-dashboard">
      {error && <div className="alert alert-error">{error}</div>}

      {children.length > 1 && (
        <div className="child-switcher" aria-label="اختيار الطفل">
          {children.map((child) => <button key={child.id} className={selectedChild?.id === child.id ? 'active' : ''} onClick={() => setSelectedChildId(child.id)}>{child.preferred_name || child.first_name}</button>)}
          <Link to="/children/new">＋</Link>
        </div>
      )}

      {selectedChild && (
        <>
          <div className="prototype-child-hero">
            <div className="child-hero-copy">
              <span className="soft-kicker">مرحبًا،</span>
              <h1>هذه {selectedChild.preferred_name || selectedChild.first_name} 💛</h1>
              <p>{selectedChild.summary || 'كل يوم خطوة جديدة نحو تطوير طفلك وتمكينه.'}</p>
              <Link className="profile-link" to={`/children/${selectedChild.id}`}>عرض الملف الشخصي ←</Link>
            </div>
            <div className="child-hero-avatar"><span>{selectedChild.first_name.slice(0, 1)}</span><small>ملف الرعاية</small></div>
          </div>

          <div className="dashboard-shortcuts">
            <Link to={`/children/${selectedChild.id}/reports`} className="dashboard-shortcut-link"><span className="shortcut-icon report">▤</span><strong>التقارير</strong><small>الملفات وسجل النسخ</small></Link>
            <div><span className="shortcut-icon appointment">▦</span><strong>المواعيد</strong><small>قريبًا</small></div>
            <div><span className="shortcut-icon goal">◎</span><strong>الأهداف</strong><small>الخطوة التالية</small></div>
            <Link to={`/children/${selectedChild.id}/care-team`} className="dashboard-shortcut-link"><span className="shortcut-icon note">♧</span><strong>فريق الرعاية</strong><small>إدارة الوصول</small></Link>
          </div>

          <div className="quick-glance-card">
            <div className="card-title-row"><div><span className="soft-kicker">نظرة سريعة</span><h2>رحلة {selectedChild.preferred_name || selectedChild.first_name} الآن</h2></div><Link to={`/children/${selectedChild.id}`}>عرض التفاصيل</Link></div>
            <div className="quick-stats">
              <article><span>الخدمات الحالية</span><strong>{selectedChild.services.length}</strong><small>{selectedChild.services[0] || 'أضيفي خدمة أولى'}</small></article>
              <article><span>الاحتياجات</span><strong>{selectedChild.needs.length}</strong><small>{selectedChild.needs[0] || 'غير مضافة بعد'}</small></article>
              <article><span>الحالات</span><strong>{selectedChild.conditions.length}</strong><small>{selectedChild.conditions[0] || 'غير مصنفة'}</small></article>
            </div>
          </div>

          <div className="today-card">
            <div className="card-title-row"><div><span className="soft-kicker">جدول اليوم</span><h2>كل ما يخص الطفل في مكان واحد</h2></div><span className="status-pill">MVP</span></div>
            <div className="timeline-placeholder">
              <span className="timeline-icon">✓</span>
              <div><strong>التعاون والوثائق أصبحا جاهزين</strong><p>فريق الرعاية والصلاحيات والتقارير وسجل النسخ أصبحت مرتبطة بملف الطفل.</p></div>
            </div>
          </div>

          <div className="add-another-row"><Link className="btn btn-white" to="/children/new">＋ إضافة طفل آخر</Link></div>
        </>
      )}
    </section>
  )
}
