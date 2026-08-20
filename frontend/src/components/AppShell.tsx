import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import WeamLogo from './WeamLogo'
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
          {user?.role === 'guardian' && <NavLink to="/children/new">إضافة طفل</NavLink>}
        </nav>

        <div className="prototype-user-menu">
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
        <span className="future-nav"><b>♧</b><small>فريقي</small></span>
        {user?.role === 'guardian' ? <Link className="add-nav" to="/children/new">＋</Link> : <span className="add-nav">＋</span>}
        <span className="future-nav"><b>◌</b><small>الرسائل</small></span>
        <button type="button" onClick={signOut}><span>•••</span><small>المزيد</small></button>
      </nav>
    </div>
  )
}
