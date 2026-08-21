import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { ChildProfile, TimelineEvent, TimelineEventType } from '../types'

const FILTERS: Array<{ key: 'all' | TimelineEventType; label: string }> = [
  { key: 'all', label: 'الكل' },
  { key: 'profile', label: 'الملف' },
  { key: 'team', label: 'الفريق' },
  { key: 'report', label: 'التقارير' },
  { key: 'goal', label: 'الأهداف' },
  { key: 'follow_up', label: 'المتابعات' },
]

const ICONS: Record<TimelineEventType, string> = {
  profile: '♡',
  team: '♧',
  report: '▤',
  goal: '◎',
  follow_up: '↻',
}

export default function TimelinePage() {
  const { childId } = useParams()
  const [child, setChild] = useState<ChildProfile | null>(null)
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [filter, setFilter] = useState<'all' | TimelineEventType>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!childId) return
    apiClient.get<ChildProfile>(`/children/${childId}`)
      .then((response) => setChild(response.data))
      .catch(() => setError('تعذر فتح ملف الطفل.'))
  }, [childId])

  useEffect(() => {
    if (!childId) return
    setLoading(true)
    setError('')
    const query = filter === 'all' ? '' : `?types=${filter}`
    apiClient.get<TimelineEvent[]>(`/children/${childId}/timeline${query}`)
      .then((response) => setEvents(response.data))
      .catch(() => setError('تعذر تحميل الخط الزمني أو لا توجد صلاحية لعرضه.'))
      .finally(() => setLoading(false))
  }, [childId, filter])

  if (!child && !error) return <div className="loading-row"><div className="spinner" /> جاري تحميل الرحلة...</div>

  return (
    <section className="m1-feature-page">
      <div className="m1-feature-hero timeline-hero">
        <div>
          <div className="m1-breadcrumb-row">
            <Link className="m1-back-link" to={child ? `/children/${child.id}` : '/dashboard'}>← العودة لملف الطفل</Link>
          </div>
          <span className="soft-kicker m1-feature-kicker">الخط الزمني</span>
          <h1>رحلة {child?.preferred_name || child?.first_name || 'الطفل'}</h1>
          <p>من إنشاء الملف إلى انضمام الفريق والتقارير وتقدم الأهداف والمتابعات؛ كل تحديث مهم يبقى واضحًا ومرتبطًا بصاحبه وتاريخه.</p>
        </div>
        <div className="m1-count-card"><strong>{events.length}</strong><span>تحديث</span></div>
      </div>

      <div className="timeline-filter-card">
        <span>تصفية الرحلة</span>
        <div className="timeline-filters">{FILTERS.map((item) => <button key={item.key} className={filter === item.key ? 'active' : ''} onClick={() => setFilter(item.key)}>{item.label}</button>)}</div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {loading ? <div className="loading-row"><div className="spinner" /> جاري تحميل التحديثات...</div> : !events.length ? (
        <div className="prototype-empty-card"><span>↻</span><h2>لا توجد تحديثات ضمن هذا التصنيف</h2><p>بمجرد حدوث نشاط جديد سيظهر هنا بترتيبه الزمني.</p></div>
      ) : (
        <div className="timeline-stream">
          {events.map((event) => (
            <article key={event.id} className={`timeline-event ${event.event_type}`}>
              <div className="timeline-event-icon">{ICONS[event.event_type]}</div>
              <div className="timeline-event-body">
                <div className="timeline-event-head"><div><span className="timeline-event-type">{FILTERS.find((item) => item.key === event.event_type)?.label}</span><h2>{event.title}</h2></div><time>{new Date(event.occurred_at).toLocaleString('ar-SA-u-ca-gregory')}</time></div>
                {event.description && <p>{event.description}</p>}
                <div className="timeline-event-actor">بواسطة <strong>{event.actor_name || 'النظام'}</strong></div>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
