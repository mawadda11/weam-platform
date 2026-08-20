import { FormEvent, useCallback, useState } from 'react'
import { AxiosError } from 'axios'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import GoogleSignInButton from '../components/GoogleSignInButton'
import WeamLogo from '../components/WeamLogo'
import { useAuth } from '../contexts/AuthContext'
import type { UserRole } from '../types'

const roles: Array<{ value: UserRole; title: string; copy: string; icon: string }> = [
  { value: 'guardian', title: 'ولي أمر', copy: 'إدارة ملفات الأطفال وفريق الرعاية', icon: '♡' },
  { value: 'care_provider', title: 'مقدم رعاية', copy: 'طبيب، أخصائي، معلم أو مقدم دعم', icon: '✦' },
  { value: 'center', title: 'مركز', copy: 'إدارة خدمات المركز وطلبات الأسر', icon: '⌂' },
]

function errorMessage(error: unknown) {
  if (error instanceof AxiosError) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail
    if (detail === 'Email is already registered') return 'يوجد حساب مسجل بهذا البريد الإلكتروني.'
    if (detail) return detail
  }
  return 'تعذر إنشاء الحساب. تحققي من البيانات وحاولي مرة أخرى.'
}

export default function RegisterPage() {
  const { user, register, loginWithGoogleCredential } = useAuth()
  const navigate = useNavigate()
  const [role, setRole] = useState<UserRole>('guardian')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [specialty, setSpecialty] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (user) return <Navigate to="/dashboard" replace />

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await register({ email, full_name: fullName, password, role, provider_specialty: role === 'care_provider' ? specialty : undefined })
      navigate(role === 'guardian' ? '/children/new' : '/dashboard', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const google = useCallback(async (credential: string) => {
    setError('')
    try {
      await loginWithGoogleCredential(credential, role, role === 'care_provider' ? specialty : undefined)
      navigate(role === 'guardian' ? '/children/new' : '/dashboard', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    }
  }, [loginWithGoogleCredential, navigate, role, specialty])

  return (
    <main className="register-page prototype-register-page">
      <header className="prototype-simple-header">
        <WeamLogo to="/" compact />
        <p>لديك حساب؟ <Link to="/login">تسجيل الدخول</Link></p>
      </header>

      <section className="prototype-register-shell">
        <div className="section-heading centered">
          <span className="soft-kicker">ابدئي بخطوة بسيطة</span>
          <h1>إنشاء حساب وئام</h1>
          <p>اختاري نوع الحساب، وبعدها نكمل المعلومات اللازمة فقط.</p>
        </div>

        <div className="prototype-role-grid">
          {roles.map((item) => (
            <button type="button" key={item.value} className={`prototype-role-card ${role === item.value ? 'selected' : ''}`} onClick={() => setRole(item.value)}>
              <span className="prototype-role-icon">{item.icon}</span>
              <strong>{item.title}</strong>
              <small>{item.copy}</small>
              <span className="role-check">✓</span>
            </button>
          ))}
        </div>

        <form className="prototype-register-form" onSubmit={submit}>
          <div className="form-grid two">
            <label>الاسم الكامل<input required minLength={2} value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="الاسم الكامل" /></label>
            <label>البريد الإلكتروني<input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@example.com" /></label>
          </div>
          {role === 'care_provider' && <label>التخصص<input required value={specialty} onChange={(e) => setSpecialty(e.target.value)} placeholder="مثال: تخاطب، سمعيات، علاج وظيفي" /></label>}
          <label>كلمة المرور<input required type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="8 أحرف على الأقل" /></label>
          {role !== 'guardian' && <div className="notice"><strong>ملاحظة التحقق</strong><p>يبدأ الحساب بحالة «غير موثّق» إلى أن تتم مراجعته إداريًا.</p></div>}
          {error && <div className="alert alert-error">{error}</div>}
          <button className="btn btn-primary btn-block btn-large" disabled={submitting}>{submitting ? 'جاري إنشاء الحساب...' : 'إنشاء الحساب'}</button>
          <div className="divider"><span>أو</span></div>
          <GoogleSignInButton onCredential={google} />
        </form>
      </section>
    </main>
  )
}
