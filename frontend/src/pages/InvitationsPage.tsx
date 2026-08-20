import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { CareInvitation } from '../types'
import '../styles/care-team.css'

const roleLabels = {
  guardian: 'ولي أمر ثانوي',
  care_provider: 'مقدم رعاية',
}

export default function InvitationsPage() {
  const [invitations, setInvitations] = useState<CareInvitation[]>([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState('')
  const [message, setMessage] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    apiClient.get<CareInvitation[]>('/care-team/invitations/mine')
      .then((response) => setInvitations(response.data))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => load(), [load])

  const respond = async (invitation: CareInvitation, action: 'accept' | 'decline') => {
    setBusyId(invitation.id)
    setMessage('')
    try {
      await apiClient.post(`/care-team/invitations/${invitation.id}/${action}`)
      setMessage(action === 'accept' ? 'تم قبول الدعوة وإضافة الملف إلى حسابك.' : 'تم رفض الدعوة.')
      load()
    } catch {
      setMessage('تعذر تنفيذ العملية. تأكدي أن الدعوة ما زالت صالحة وأن نوع الحساب مطابق للدعوة.')
    } finally {
      setBusyId('')
    }
  }

  return (
    <section className="care-team-page invitations-page">
      <div className="care-team-heading">
        <div><span className="soft-kicker">الوصول بموافقتك</span><h1>دعوات فريق الرعاية</h1><p>لن يظهر أي ملف في حسابك حتى تقبلي الدعوة بنفسك.</p></div>
        <Link className="btn btn-outline" to="/dashboard">العودة للرئيسية</Link>
      </div>
      {message && <div className="care-team-notice">{message}</div>}
      {loading ? <div className="loading-row"><div className="spinner" /> جاري تحميل الدعوات...</div> : invitations.length ? (
        <div className="invitation-list">
          {invitations.map((invitation) => (
            <article className="invitation-card" key={invitation.id}>
              <div className="invitation-icon">✉</div>
              <div className="invitation-copy">
                <span>{roleLabels[invitation.target_role]}</span>
                <h2>{invitation.child_name}</h2>
                <p>{invitation.role_label || 'عضو في فريق الرعاية'} · {invitation.access_expires_at ? `الوصول حتى ${new Date(invitation.access_expires_at).toLocaleDateString('ar-SA')}` : 'وصول مستمر حتى الإلغاء'}</p>
                <small>تنتهي صلاحية الدعوة في {new Date(invitation.invitation_expires_at).toLocaleDateString('ar-SA')}</small>
              </div>
              <div className="invitation-actions">
                <button className="btn btn-primary" disabled={busyId === invitation.id} onClick={() => respond(invitation, 'accept')}>قبول</button>
                <button className="btn btn-outline" disabled={busyId === invitation.id} onClick={() => respond(invitation, 'decline')}>رفض</button>
              </div>
            </article>
          ))}
        </div>
      ) : <div className="prototype-empty-card"><span>✓</span><h2>لا توجد دعوات معلقة</h2><p>أي دعوة جديدة مرتبطة ببريد حسابك ستظهر هنا.</p></div>}
    </section>
  )
}
