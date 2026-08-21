import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { NotificationItem } from '../types'
import '../styles/m3-followups-notifications.css'

const TYPE_META: Record<string, { icon: string; label: string }> = {
  invitation: { icon: '✉', label: 'دعوة' },
  report: { icon: '▤', label: 'تقرير' },
  goal: { icon: '◎', label: 'هدف' },
  goal_deadline: { icon: '◷', label: 'موعد هدف' },
  message: { icon: '💬', label: 'رسالة' },
  follow_up: { icon: '↻', label: 'متابعة' },
}

export default function NotificationsPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState<NotificationItem[]>([])
  const [filter, setFilter] = useState<'all' | 'unread'>('unread')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = async () => {
    const response = await apiClient.get<NotificationItem[]>('/notifications')
    setItems(response.data)
  }

  useEffect(() => {
    setLoading(true)
    void load()
      .catch(() => setError('تعذر تحميل التنبيهات.'))
      .finally(() => setLoading(false))
  }, [])

  const unreadCount = useMemo(() => items.filter((item) => !item.is_read).length, [items])
  const visible = filter === 'unread' ? items.filter((item) => !item.is_read) : items

  const mark = async (eventKeys: string[]) => {
    if (!eventKeys.length) return
    await apiClient.post('/notifications/read', { event_keys: eventKeys })
    setItems((current) => current.map((item) => eventKeys.includes(item.event_key) ? { ...item, is_read: true } : item))
    window.dispatchEvent(new Event('weam:notifications-changed'))
  }

  const openItem = async (item: NotificationItem) => {
    try {
      if (!item.is_read) await mark([item.event_key])
    } finally {
      navigate(item.url)
    }
  }

  const markAll = async () => {
    if (busy || unreadCount === 0) return
    setBusy(true)
    setError('')
    try {
      await apiClient.post('/notifications/read-all')
      setItems((current) => current.map((item) => ({ ...item, is_read: true })))
      window.dispatchEvent(new Event('weam:notifications-changed'))
    } catch {
      setError('تعذر تعليم التنبيهات كمقروءة.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="m3-page">
      <div className="m3-hero notifications-hero">
        <div>
          <span className="soft-kicker">التنبيهات</span>
          <h1>ما يحتاج انتباهك الآن</h1>
          <p>تجمع وئام التنبيهات المهمة من الدعوات، التقارير، الأهداف، الرسائل والمتابعات القريبة في مكان واحد.</p>
        </div>
        <div className="notification-hero-count">
          <strong>{unreadCount}</strong>
          <span>غير مقروء</span>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="m3-toolbar">
        <div className="m3-filter-tabs">
          <button className={filter === 'unread' ? 'active' : ''} onClick={() => setFilter('unread')}>غير المقروء</button>
          <button className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>الكل</button>
        </div>
        <button className="btn btn-white btn-small" onClick={() => void markAll()} disabled={busy || unreadCount === 0}>
          ✓ تعليم الكل كمقروء
        </button>
      </div>

      {loading ? (
        <div className="loading-row"><div className="spinner" /> جاري تحميل التنبيهات...</div>
      ) : !visible.length ? (
        <div className="prototype-empty-card">
          <span>🔔</span>
          <h2>{filter === 'unread' ? 'لا توجد تنبيهات جديدة' : 'لا توجد تنبيهات بعد'}</h2>
          <p>عند وصول تحديث مهم سيظهر هنا تلقائيًا.</p>
        </div>
      ) : (
        <div className="notification-list">
          {visible.map((item) => {
            const meta = TYPE_META[item.notification_type] || { icon: '•', label: 'تحديث' }
            return (
              <button
                key={item.event_key}
                className={`notification-card ${item.is_read ? 'read' : 'unread'}`}
                onClick={() => void openItem(item)}
              >
                <span className="notification-type-icon">{meta.icon}</span>
                <div className="notification-card-body">
                  <div className="notification-card-head">
                    <span>{meta.label}</span>
                    <time>{new Date(item.occurred_at).toLocaleString('ar-SA-u-ca-gregory')}</time>
                  </div>
                  <strong>{item.title}</strong>
                  <p>{item.body}</p>
                </div>
                {!item.is_read && <span className="notification-unread-dot" aria-label="غير مقروء" />}
              </button>
            )
          })}
        </div>
      )}
    </section>
  )
}
