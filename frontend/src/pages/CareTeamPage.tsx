import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { CareTeamMember, CareTeamOverview, ChildProfile } from '../types'
import '../styles/care-team.css'

const permissions = [
  ['view_profile', 'عرض ملف الطفل'],
  ['view_care_team', 'عرض فريق الرعاية'],
  ['view_reports', 'عرض التقارير'],
  ['upload_reports', 'رفع التقارير'],
  ['view_goals', 'عرض الأهداف'],
  ['manage_goals', 'تحديث الأهداف'],
  ['view_timeline', 'عرض الخط الزمني'],
  ['message_team', 'التواصل مع الفريق'],
] as const

const defaultProviderPermissions = permissions.map(([value]) => value)
const defaultGuardianPermissions = ['view_profile', 'view_care_team', 'view_reports', 'view_goals', 'view_timeline', 'message_team']

function MemberEditor({ childId, member, onChanged }: { childId: string; member: CareTeamMember; onChanged: () => void }) {
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState<string[]>(member.permissions)
  const [days, setDays] = useState('')
  const [busy, setBusy] = useState(false)

  const toggle = (permission: string) => setSelected((current) => current.includes(permission) ? current.filter((item) => item !== permission) : [...current, permission])

  const save = async () => {
    setBusy(true)
    try {
      await apiClient.patch(`/children/${childId}/care-team/members/${member.membership_id}`, {
        permissions: selected,
        access_days: days ? Number(days) : null,
      })
      setOpen(false)
      onChanged()
    } finally {
      setBusy(false)
    }
  }

  const revoke = async () => {
    if (!window.confirm(`إلغاء وصول ${member.full_name} إلى ملف الطفل؟`)) return
    setBusy(true)
    try {
      await apiClient.delete(`/children/${childId}/care-team/members/${member.membership_id}`)
      onChanged()
    } finally {
      setBusy(false)
    }
  }

  if (member.is_primary_guardian) return <span className="primary-owner-label">التحكم الرئيسي</span>

  return (
    <div className="member-admin-actions">
      <button className="text-action" onClick={() => setOpen((value) => !value)}>تعديل الوصول</button>
      <button className="text-action danger" disabled={busy} onClick={revoke}>إلغاء الوصول</button>
      {open && (
        <div className="member-editor">
          <div className="permission-grid compact">
            {permissions.map(([value, label]) => <label key={value}><input type="checkbox" checked={selected.includes(value)} onChange={() => toggle(value)} /><span>{label}</span></label>)}
          </div>
          <label className="field-label">مدة جديدة للوصول<select value={days} onChange={(event) => setDays(event.target.value)}><option value="">بدون تاريخ انتهاء</option><option value="30">30 يومًا</option><option value="90">90 يومًا</option><option value="180">180 يومًا</option><option value="365">سنة</option></select></label>
          <button className="btn btn-primary btn-small" disabled={busy} onClick={save}>حفظ الصلاحيات</button>
        </div>
      )}
    </div>
  )
}

export default function CareTeamPage() {
  const { childId } = useParams()
  const [child, setChild] = useState<ChildProfile | null>(null)
  const [overview, setOverview] = useState<CareTeamOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [email, setEmail] = useState('')
  const [targetRole, setTargetRole] = useState<'care_provider' | 'guardian'>('care_provider')
  const [roleLabel, setRoleLabel] = useState('')
  const [accessDays, setAccessDays] = useState('90')
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>(defaultProviderPermissions)
  const [submitting, setSubmitting] = useState(false)

  const canManageTeam = useMemo(() => child?.access_role === 'guardian' && (child.guardian_type === 'primary' || child.access_permissions.includes('manage_care_team')), [child])
  const canManagePermissions = useMemo(() => child?.access_role === 'guardian' && (child.guardian_type === 'primary' || child.access_permissions.includes('manage_permissions')), [child])

  const load = useCallback(async () => {
    if (!childId) return
    setLoading(true)
    setError('')
    try {
      const [childResponse, teamResponse] = await Promise.all([
        apiClient.get<ChildProfile>(`/children/${childId}`),
        apiClient.get<CareTeamOverview>(`/children/${childId}/care-team`),
      ])
      setChild(childResponse.data)
      setOverview(teamResponse.data)
    } catch {
      setError('تعذر تحميل فريق الرعاية أو لا توجد لديك الصلاحية المطلوبة.')
    } finally {
      setLoading(false)
    }
  }, [childId])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    setSelectedPermissions(targetRole === 'guardian' ? defaultGuardianPermissions : defaultProviderPermissions)
  }, [targetRole])

  const togglePermission = (permission: string) => setSelectedPermissions((current) => current.includes(permission) ? current.filter((item) => item !== permission) : [...current, permission])

  const submitInvitation = async (event: FormEvent) => {
    event.preventDefault()
    if (!childId) return
    setSubmitting(true)
    setError('')
    try {
      await apiClient.post(`/children/${childId}/care-team/invitations`, {
        email,
        target_role: targetRole,
        role_label: roleLabel || null,
        permissions: selectedPermissions,
        access_days: accessDays ? Number(accessDays) : null,
      })
      setEmail('')
      setRoleLabel('')
      await load()
    } catch (requestError: any) {
      const detail = requestError?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'تعذر إرسال الدعوة. تأكدي من البريد والصلاحيات.')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <div className="loading-row"><div className="spinner" /> جاري تحميل فريق الرعاية...</div>
  if (!child || !overview) return <div className="prototype-empty-card"><h2>تعذر فتح فريق الرعاية</h2><p>{error}</p><Link className="btn btn-primary" to="/dashboard">الرئيسية</Link></div>

  return (
    <section className="care-team-page">
      <div className="care-team-heading">
        <div><span className="soft-kicker">فريق واحد · وصول واضح</span><h1>فريق رعاية {child.preferred_name || child.first_name}</h1><p>ولي الأمر يحدد من يرى ماذا، ومدة الوصول، ويمكنه إلغاء الصلاحية في أي وقت.</p></div>
        <Link className="btn btn-outline" to={`/children/${child.id}`}>العودة لملف الطفل</Link>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="care-team-summary-grid">
        <article><span>أعضاء الفريق</span><strong>{overview.members.filter((member) => member.access_status === 'active').length}</strong><small>يشمل أولياء الأمر ومقدمي الرعاية</small></article>
        <article><span>دعوات معلقة</span><strong>{overview.pending_invitations.length}</strong><small>لم يتم قبولها بعد</small></article>
        <article><span>التحكم</span><strong>{canManageTeam ? 'بيد ولي الأمر' : 'حسب صلاحيتك'}</strong><small>كل وصول موثق وقابل للإلغاء</small></article>
      </div>

      {canManageTeam && (
        <form className="invite-panel" onSubmit={submitInvitation}>
          <div className="section-heading"><div><span className="soft-kicker">دعوة جديدة</span><h2>أضيفي عضوًا إلى الفريق</h2></div><span className="step-pill">01</span></div>
          <div className="invite-fields">
            <label className="field-label">نوع العضو<select value={targetRole} onChange={(event) => setTargetRole(event.target.value as 'care_provider' | 'guardian')}><option value="care_provider">مقدم رعاية</option><option value="guardian">ولي أمر ثانوي</option></select></label>
            <label className="field-label">البريد الإلكتروني<input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="name@example.com" /></label>
            <label className="field-label">الدور داخل الفريق<input value={roleLabel} onChange={(event) => setRoleLabel(event.target.value)} placeholder={targetRole === 'care_provider' ? 'مثال: أخصائي تخاطب' : 'مثال: والد'} /></label>
            <label className="field-label">مدة الوصول<select value={accessDays} onChange={(event) => setAccessDays(event.target.value)}><option value="">مستمر حتى الإلغاء</option><option value="30">30 يومًا</option><option value="90">90 يومًا</option><option value="180">180 يومًا</option><option value="365">سنة</option></select></label>
          </div>
          <div className="permission-section"><strong>حددي الصلاحيات قبل إرسال الدعوة</strong><p>يمكن تعديلها أو إلغاؤها لاحقًا.</p><div className="permission-grid">{permissions.map(([value, label]) => <label key={value}><input type="checkbox" checked={selectedPermissions.includes(value)} onChange={() => togglePermission(value)} /><span>{label}</span></label>)}</div></div>
          <button className="btn btn-primary invite-submit" disabled={submitting}>{submitting ? 'جاري الإرسال...' : 'إرسال الدعوة'}</button>
        </form>
      )}

      <div className="team-section">
        <div className="section-heading"><div><span className="soft-kicker">الفريق الحالي</span><h2>من لديه وصول إلى الملف؟</h2></div></div>
        <div className="team-member-list">
          {overview.members.map((member) => (
            <article className={`team-member-card ${member.access_status === 'revoked' ? 'revoked' : ''}`} key={member.membership_id}>
              <div className="team-avatar">{member.full_name.slice(0, 1)}</div>
              <div className="team-member-copy"><div className="member-title-row"><h3>{member.full_name}</h3>{member.verification_status === 'verified' ? <span className="status-pill success">موثّق</span> : <span className="status-pill warning">غير موثّق</span>}</div><p>{member.role_label || 'عضو فريق الرعاية'}</p><small>{member.email}</small><div className="member-permission-chips">{member.permissions.slice(0, 4).map((permission) => <span key={permission}>{permissions.find(([value]) => value === permission)?.[1] || permission}</span>)}</div><small>{member.expires_at ? `الوصول حتى ${new Date(member.expires_at).toLocaleDateString('ar-SA')}` : 'الوصول مستمر حتى الإلغاء'}</small></div>
              {canManagePermissions && <MemberEditor childId={child.id} member={member} onChanged={load} />}
            </article>
          ))}
        </div>
      </div>

      {canManageTeam && overview.pending_invitations.length > 0 && (
        <div className="team-section pending-section"><div className="section-heading"><div><span className="soft-kicker">بانتظار الموافقة</span><h2>الدعوات المعلقة</h2></div></div><div className="pending-invite-grid">{overview.pending_invitations.map((invitation) => <article key={invitation.id}><span>✉</span><div><strong>{invitation.email}</strong><p>{invitation.role_label || (invitation.target_role === 'guardian' ? 'ولي أمر ثانوي' : 'مقدم رعاية')}</p><small>تنتهي الدعوة {new Date(invitation.invitation_expires_at).toLocaleDateString('ar-SA')}</small></div></article>)}</div></div>
      )}
    </section>
  )
}
