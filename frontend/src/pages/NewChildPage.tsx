import { FormEvent, useState } from 'react'
import { AxiosError } from 'axios'
import { Navigate, useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import TagEditor from '../components/TagEditor'
import { useAuth } from '../contexts/AuthContext'
import type { ChildInput, ChildProfile } from '../types'

const initial: ChildInput = { first_name: '', preferred_name: '', birth_date: '', gender: '', conditions: [], needs: [], support_requirements: [], services: [], summary: '' }

export default function NewChildPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState<ChildInput>(initial)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  if (user?.role !== 'guardian') return <Navigate to="/dashboard" replace />

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const payload = { ...form, preferred_name: form.preferred_name || undefined, birth_date: form.birth_date || undefined, gender: form.gender || undefined, summary: form.summary || undefined }
      const response = await apiClient.post<ChildProfile>('/children', payload)
      navigate(`/children/${response.data.id}`, { replace: true })
    } catch (err) {
      if (err instanceof AxiosError && err.response?.status === 422) setError('راجعي البيانات المدخلة. تاريخ الميلاد لا يمكن أن يكون في المستقبل.')
      else setError('تعذر إنشاء ملف الطفل. حاولي مرة أخرى.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="prototype-child-form-page">
      <div className="child-form-heading">
        <span className="soft-kicker">ملف طفل جديد</span>
        <h1>نبدأ بالمعلومات الأساسية فقط 💛</h1>
        <p>يمكنك إكمال باقي التفاصيل لاحقًا، ووئام يدعم أكثر من حالة واحتياج.</p>
      </div>

      <div className="form-progress"><span className="active">1</span><i /><span>2</span><i /><span>3</span></div>

      <form className="prototype-child-form" onSubmit={submit}>
        <section className="prototype-form-section identity-section">
          <div className="prototype-form-section-heading"><span>1</span><div><h2>بيانات الطفل</h2><p>معلومات أساسية تُفصل تقنيًا عن بيانات الرعاية.</p></div></div>
          <div className="form-grid two">
            <label>اسم الطفل *<input required value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} placeholder="الاسم الأول" /></label>
            <label>الاسم المفضل<input value={form.preferred_name} onChange={(e) => setForm({ ...form, preferred_name: e.target.value })} placeholder="اختياري" /></label>
            <label>تاريخ الميلاد<input type="date" max={new Date().toISOString().slice(0, 10)} value={form.birth_date} onChange={(e) => setForm({ ...form, birth_date: e.target.value })} /></label>
            <label>الجنس<select value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })}><option value="">غير محدد</option><option value="female">أنثى</option><option value="male">ذكر</option><option value="other">أخرى / أفضل عدم التحديد</option></select></label>
          </div>
        </section>

        <section className="prototype-form-section care-section">
          <div className="prototype-form-section-heading"><span>2</span><div><h2>ملف الرعاية</h2><p>أضيفي ما تعرفينه الآن، ويمكن تعديله في أي وقت.</p></div></div>
          <div className="care-fields-grid">
            <TagEditor label="الحالة أو الحالات" value={form.conditions} onChange={(conditions) => setForm({ ...form, conditions })} placeholder="مثال: ضعف سمع" />
            <TagEditor label="الاحتياجات" value={form.needs} onChange={(needs) => setForm({ ...form, needs })} placeholder="مثال: دعم التواصل" />
            <TagEditor label="متطلبات الدعم" value={form.support_requirements} onChange={(support_requirements) => setForm({ ...form, support_requirements })} placeholder="مثال: تعليمات مرئية" />
            <TagEditor label="الخدمات الحالية" value={form.services} onChange={(services) => setForm({ ...form, services })} placeholder="مثال: تخاطب" />
          </div>
          <label>ملخص اختياري<textarea rows={4} maxLength={3000} value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} placeholder="معلومات مختصرة تساعد فريق الرعاية لاحقًا..." /></label>
        </section>

        {error && <div className="alert alert-error">{error}</div>}
        <div className="prototype-form-actions"><button type="button" className="btn btn-white" onClick={() => navigate('/dashboard')}>إلغاء</button><button className="btn btn-primary btn-large" disabled={submitting}>{submitting ? 'جاري الحفظ...' : 'حفظ ملف الطفل'}</button></div>
      </form>
    </section>
  )
}
