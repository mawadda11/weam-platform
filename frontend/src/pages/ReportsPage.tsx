import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiClient } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import type { CareTeamOverview, ChildProfile, ChildReport, ReportVersion } from '../types'
import '../styles/reports.css'

const REPORT_TYPES = [
  'سمعيات',
  'تخاطب ولغة',
  'سلوك',
  'علاج وظيفي',
  'علاج طبيعي',
  'تقرير طبي',
  'تقرير تعليمي',
  'تقييم',
  'أخرى',
]

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function fileIcon(contentType?: string) {
  if (contentType === 'application/pdf') return 'PDF'
  return 'IMG'
}

export default function ReportsPage() {
  const { childId } = useParams()
  const { user } = useAuth()
  const [child, setChild] = useState<ChildProfile | null>(null)
  const [reports, setReports] = useState<ChildReport[]>([])
  const [team, setTeam] = useState<CareTeamOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [historyOpen, setHistoryOpen] = useState<string | null>(null)
  const [selectedUsers, setSelectedUsers] = useState<string[]>([])
  const [visibility, setVisibility] = useState<'care_team' | 'restricted'>('care_team')

  const canUpload = Boolean(child && (child.guardian_type === 'primary' || child.access_permissions.includes('upload_reports')))
  const canManage = Boolean(child && (child.guardian_type === 'primary' || child.access_permissions.includes('manage_permissions')))

  const loadReports = async () => {
    if (!childId) return
    const response = await apiClient.get<ChildReport[]>(`/children/${childId}/reports`)
    setReports(response.data)
  }

  useEffect(() => {
    if (!childId) return
    let active = true
    const load = async () => {
      setLoading(true)
      setError('')
      try {
        const childResponse = await apiClient.get<ChildProfile>(`/children/${childId}`)
        if (!active) return
        setChild(childResponse.data)
        const reportsResponse = await apiClient.get<ChildReport[]>(`/children/${childId}/reports`)
        if (!active) return
        setReports(reportsResponse.data)
        const manager = childResponse.data.guardian_type === 'primary' || childResponse.data.access_permissions.includes('manage_permissions')
        if (manager) {
          try {
            const teamResponse = await apiClient.get<CareTeamOverview>(`/children/${childId}/care-team`)
            if (active) setTeam(teamResponse.data)
          } catch {
            if (active) setTeam(null)
          }
        }
      } catch {
        if (active) setError('تعذر تحميل التقارير، أو لا توجد لديك صلاحية لعرضها.')
      } finally {
        if (active) setLoading(false)
      }
    }
    void load()
    return () => { active = false }
  }, [childId])

  const selectableMembers = useMemo(
    () => (team?.members ?? []).filter((member) => member.access_status === 'active' && member.user_id !== user?.id),
    [team, user?.id],
  )

  const memberNames = useMemo(() => {
    const result = new Map<string, string>()
    for (const member of team?.members ?? []) result.set(member.user_id, member.full_name)
    return result
  }, [team])

  const submitReport = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!childId) return
    const form = event.currentTarget
    const formData = new FormData(form)
    formData.set('visibility', visibility)
    formData.set('allowed_user_ids_json', JSON.stringify(visibility === 'restricted' ? selectedUsers : []))
    setSubmitting(true)
    setError('')
    setNotice('')
    try {
      await apiClient.post(`/children/${childId}/reports`, formData)
      await loadReports()
      form.reset()
      setVisibility('care_team')
      setSelectedUsers([])
      setUploadOpen(false)
      setNotice('تم رفع التقرير وحفظ النسخة الأولى بنجاح.')
    } catch {
      setError('تعذر رفع التقرير. تأكدي أن الملف PDF أو PNG أو JPG وحجمه لا يتجاوز 15MB.')
    } finally {
      setSubmitting(false)
    }
  }

  const uploadVersion = async (reportId: string, file: File | undefined) => {
    if (!file) return
    const data = new FormData()
    data.append('file', file)
    data.append('notes', 'نسخة محدثة')
    setError('')
    setNotice('')
    try {
      await apiClient.post(`/reports/${reportId}/versions`, data)
      await loadReports()
      setHistoryOpen(reportId)
      setNotice('تمت إضافة نسخة جديدة مع الاحتفاظ بالنسخ السابقة.')
    } catch {
      setError('تعذر رفع النسخة الجديدة. تحققي من نوع الملف والصلاحية.')
    }
  }

  const downloadVersion = async (report: ChildReport, version: ReportVersion) => {
    setError('')
    try {
      const response = await apiClient.get(
        `/reports/${report.id}/versions/${version.id}/download`,
        { responseType: 'blob' },
      )
      const url = URL.createObjectURL(response.data)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = version.original_filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
    } catch {
      setError('تعذر تنزيل هذا الملف.')
    }
  }

  const archiveReport = async (reportId: string) => {
    if (!window.confirm('هل تريدين أرشفة هذا التقرير؟ سيبقى محفوظًا في السجل ولن يُحذف الملف.')) return
    try {
      await apiClient.delete(`/reports/${reportId}`)
      await loadReports()
      setNotice('تمت أرشفة التقرير مع الاحتفاظ بسجل نسخه.')
    } catch {
      setError('تعذر أرشفة التقرير.')
    }
  }

  const toggleSelectedUser = (userId: string) => {
    setSelectedUsers((current) => current.includes(userId)
      ? current.filter((id) => id !== userId)
      : [...current, userId])
  }

  if (loading) return <div className="loading-row"><div className="spinner" /> جاري تحميل التقارير...</div>

  if (error && !child) {
    return <div className="prototype-empty-card"><h2>تعذر فتح التقارير</h2><p>{error}</p><Link className="btn btn-primary" to="/dashboard">العودة للرئيسية</Link></div>
  }

  if (!child) return null

  return (
    <section className="reports-page">
      <div className="reports-hero">
        <div>
          <Link className="reports-back" to={`/children/${child.id}`}>→ العودة لملف الطفل</Link>
          <span className="soft-kicker">التقارير والوثائق</span>
          <h1>تقارير {child.preferred_name || child.first_name}</h1>
          <p>كل تقرير محفوظ بنسخه السابقة وصلاحياته، ليبقى فريق الرعاية على نفس الصورة.</p>
        </div>
        <div className="reports-hero-actions">
          <span className="reports-count"><strong>{reports.length}</strong><small>تقرير نشط</small></span>
          {canUpload && <button className="btn btn-primary" type="button" onClick={() => setUploadOpen((value) => !value)}>＋ رفع تقرير</button>}
        </div>
      </div>

      {notice && <div className="alert alert-success">{notice}</div>}
      {error && <div className="alert alert-error">{error}</div>}

      {uploadOpen && canUpload && (
        <form className="report-upload-card" onSubmit={submitReport}>
          <div className="report-form-heading"><span>▤</span><div><h2>إضافة تقرير جديد</h2><p>PDF أو PNG أو JPG — بحد أقصى 15MB</p></div></div>
          <div className="report-form-grid">
            <label><span>عنوان التقرير *</span><input name="title" required maxLength={220} placeholder="مثال: تقرير تقييم السمع" /></label>
            <label><span>نوع التقرير *</span><select name="report_type" required defaultValue=""><option value="" disabled>اختاري النوع</option>{REPORT_TYPES.map((type) => <option key={type}>{type}</option>)}</select></label>
            <label><span>تاريخ التقرير</span><input name="report_date" type="date" /></label>
            <label><span>الجهة / المختص</span><input name="source_label" maxLength={180} placeholder="مثال: مركز السمع والتوازن" /></label>
            <label className="report-file-field"><span>الملف *</span><input name="file" type="file" accept="application/pdf,image/png,image/jpeg" required /></label>
            <label><span>ملاحظة على النسخة</span><input name="notes" maxLength={3000} placeholder="اختياري" /></label>
          </div>

          {canManage && (
            <div className="report-visibility-box">
              <div><strong>من يستطيع رؤية التقرير؟</strong><small>ولي الأمر الرئيسي يستطيع الوصول دائمًا.</small></div>
              <div className="visibility-options">
                <button type="button" className={visibility === 'care_team' ? 'active' : ''} onClick={() => setVisibility('care_team')}><b>فريق الرعاية</b><span>كل عضو لديه صلاحية عرض التقارير</span></button>
                <button type="button" className={visibility === 'restricted' ? 'active' : ''} onClick={() => setVisibility('restricted')}><b>أعضاء محددون</b><span>اختاري من الفريق لهذا التقرير فقط</span></button>
              </div>
              {visibility === 'restricted' && (
                <div className="restricted-members">
                  {selectableMembers.length ? selectableMembers.map((member) => (
                    <label key={member.user_id} className={selectedUsers.includes(member.user_id) ? 'selected' : ''}>
                      <input type="checkbox" checked={selectedUsers.includes(member.user_id)} onChange={() => toggleSelectedUser(member.user_id)} />
                      <span>{member.full_name}<small>{member.role_label || member.account_role}</small></span>
                    </label>
                  )) : <p>لا يوجد أعضاء آخرون في فريق الرعاية حاليًا.</p>}
                </div>
              )}
            </div>
          )}

          <div className="report-form-actions"><button className="btn btn-white" type="button" onClick={() => setUploadOpen(false)}>إلغاء</button><button className="btn btn-primary" disabled={submitting}>{submitting ? 'جاري الرفع...' : 'حفظ التقرير'}</button></div>
        </form>
      )}

      {!reports.length ? (
        <div className="prototype-empty-card report-empty"><span>▤</span><h2>لا توجد تقارير بعد</h2><p>عند إضافة أول تقرير سيظهر هنا مع سجل النسخ والجهة والتاريخ وصلاحيات الوصول.</p>{canUpload && <button className="btn btn-primary" onClick={() => setUploadOpen(true)}>رفع أول تقرير</button>}</div>
      ) : (
        <div className="reports-list">
          {reports.map((report) => {
            const latest = report.versions[0]
            const historyVisible = historyOpen === report.id
            return (
              <article className="report-card" key={report.id}>
                <div className="report-card-main">
                  <div className="report-file-icon">{fileIcon(latest?.content_type)}</div>
                  <div className="report-card-copy">
                    <div className="report-title-row"><div><span className="report-type-pill">{report.report_type}</span>{report.visibility === 'restricted' && <span className="report-private-pill">وصول محدد</span>}<h2>{report.title}</h2></div><small>{report.report_date ? new Date(`${report.report_date}T00:00:00`).toLocaleDateString('ar-SA-u-ca-gregory') : new Date(report.created_at).toLocaleDateString('ar-SA-u-ca-gregory')}</small></div>
                    <p>{report.source_label || 'بدون جهة محددة'} · أضيف بواسطة {report.created_by_name}</p>
                    <div className="report-meta-row"><span>{report.versions.length} {report.versions.length === 1 ? 'نسخة' : 'نسخ'}</span>{latest && <span>{formatSize(latest.size_bytes)}</span>}<span>{report.visibility === 'care_team' ? 'متاح لفريق الرعاية المصرح' : `${report.allowed_user_ids.length} أعضاء محددين`}</span></div>
                  </div>
                  <div className="report-card-actions">
                    {latest && <button className="btn btn-primary btn-small" onClick={() => void downloadVersion(report, latest)}>تنزيل</button>}
                    {latest && <Link className="btn btn-white btn-small" to={`/reports/${report.id}/ai`}>✦ تحليل AI</Link>}
                    <button className="btn btn-white btn-small" onClick={() => setHistoryOpen(historyVisible ? null : report.id)}>{historyVisible ? 'إخفاء النسخ' : 'سجل النسخ'}</button>
                    {canUpload && <label className="btn btn-white btn-small report-version-button">نسخة جديدة<input type="file" accept="application/pdf,image/png,image/jpeg" onChange={(event) => { void uploadVersion(report.id, event.target.files?.[0]); event.currentTarget.value = '' }} /></label>}
                    {canManage && <button className="report-archive-button" type="button" onClick={() => void archiveReport(report.id)}>أرشفة</button>}
                  </div>
                </div>

                {report.visibility === 'restricted' && canManage && (
                  <div className="report-access-note">الوصول المحدد: {report.allowed_user_ids.map((id) => memberNames.get(id) || 'عضو فريق').join('، ') || 'ولي الأمر الرئيسي فقط'}</div>
                )}

                {historyVisible && (
                  <div className="report-history">
                    <div className="report-history-title"><strong>سجل النسخ</strong><span>الملفات السابقة لا يتم استبدالها أو حذفها</span></div>
                    {report.versions.map((version) => (
                      <div className="report-version-row" key={version.id}>
                        <span className="version-number">v{version.version_number}</span>
                        <div><strong>{version.original_filename}</strong><small>{new Date(version.created_at).toLocaleString('ar-SA-u-ca-gregory')} · {version.uploaded_by_name}{version.notes ? ` · ${version.notes}` : ''}</small></div>
                        <span>{formatSize(version.size_bytes)}</span>
                        <button type="button" onClick={() => void downloadVersion(report, version)}>تنزيل</button>
                      </div>
                    ))}
                  </div>
                )}
              </article>
            )
          })}
        </div>
      )}

      <div className="reports-security-note"><span>🔒</span><div><strong>صلاحيات التقارير مرتبطة بفريق الرعاية</strong><p>لا يستطيع أي عضو فتح أو تنزيل تقرير إلا إذا كان وصوله للطفل نشطًا ولديه صلاحية عرض التقارير، ويمكن لولي الأمر تقييد تقرير بعينه لأعضاء محددين.</p></div></div>
    </section>
  )
}
