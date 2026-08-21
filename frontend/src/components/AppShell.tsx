import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import WeamLogo from './WeamLogo'
import { apiClient } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

const roleLabels = {
  guardian: 'ولي أمر',
  care_provider: 'مقدم رعاية',
  center: 'مركز',
  admin: 'إدارة',
}

export default function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [unread, setUnread] = useState(0)

  useEffect(() => {
    let mounted = true
    const load = () => {
      apiClient.get<{ count: number }>('/notifications/unread-count')
        .then((response) => {
          if (mounted) setUnread(response.data.count)
        })
        .catch(() => undefined)
    }
    load()
    const timer = window.setInterval(load, 30000)
    const refresh = () => load()
    window.addEventListener('weam:notifications-changed', refresh)
    return () => {
      mounted = false
      window.clearInterval(timer)
      window.removeEventListener('weam:notifications-changed', refresh)
    }
  }, [])

  const signOut = () => {
    logout()
    navigate('/')
  }

  return (
    <div className="app-layout prototype-app-layout">
      <header className="prototype-topbar">
        <WeamLogo to="/dashboard" compact />

        <nav className="prototype-main-nav" aria-label="التنقل الرئيسي">
          <NavLink to="/dashboard">الرئيسية</NavLink>
          <NavLink to="/invitations">الدعوات</NavLink>
          <NavLink to="/notifications" className="notification-nav-link">
            التنبيهات
            {unread > 0 && <span className="notification-nav-badge">{unread > 99 ? '99+' : unread}</span>}
          </NavLink>
          {user?.role === 'guardian' && <NavLink to="/children/new">إضافة طفل</NavLink>}
        </nav>

        <div className="prototype-user-menu">
          <Link className="notification-bell-button" to="/notifications" aria-label={`التنبيهات غير المقروءة ${unread}`}>
            <span>🔔</span>
            {unread > 0 && <b>{unread > 99 ? '99+' : unread}</b>}
          </Link>
          <div className="user-copy">
            <strong>{user?.full_name}</strong>
            <span>{user ? roleLabels[user.role] : ''}</span>
          </div>
          <button className="btn btn-outline btn-small" onClick={signOut}>تسجيل الخروج</button>
        </div>
      </header>

      <main className="prototype-page-wrap"><Outlet /></main>

      <nav className="mobile-bottom-nav" aria-label="التنقل السفلي">
        <NavLink to="/dashboard"><span>⌂</span><small>الرئيسية</small></NavLink>
        <NavLink to="/invitations"><span>✉</span><small>الدعوات</small></NavLink>
        {user?.role === 'guardian' ? <Link className="add-nav" to="/children/new">＋</Link> : <span className="add-nav">و</span>}
        <NavLink to="/notifications" className="mobile-notification-link">
          <span>🔔{unread > 0 && <b>{unread > 9 ? '9+' : unread}</b>}</span>
          <small>التنبيهات</small>
        </NavLink>
        <button type="button" onClick={signOut}><span>•••</span><small>المزيد</small></button>
      </nav>
    </div>
  )
}
