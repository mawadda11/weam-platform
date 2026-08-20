import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './components/AppShell'
import ProtectedRoute from './components/ProtectedRoute'
import CareTeamPage from './pages/CareTeamPage'
import ChildDetailPage from './pages/ChildDetailPage'
import DashboardPage from './pages/DashboardPage'
import HomePage from './pages/HomePage'
import InvitationsPage from './pages/InvitationsPage'
import LoginPage from './pages/LoginPage'
import NewChildPage from './pages/NewChildPage'
import RegisterPage from './pages/RegisterPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/invitations" element={<InvitationsPage />} />
          <Route path="/children/new" element={<NewChildPage />} />
          <Route path="/children/:childId" element={<ChildDetailPage />} />
          <Route path="/children/:childId/care-team" element={<CareTeamPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
