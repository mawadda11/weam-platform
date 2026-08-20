import { FormEvent, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { AxiosError } from 'axios'
import GoogleSignInButton from '../components/GoogleSignInButton'
import WeamLogo from '../components/WeamLogo'
import { useAuth } from '../contexts/AuthContext'

function errorMessage(error: unknown) {
  if (error instanceof AxiosError) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail
    if (detail === 'Invalid email or password') return 'البريد الإلكتروني أو كلمة المرور غير صحيحة.'
    if (detail) return detail
  }
  return 'تعذر تسجيل الدخول. حاولي مرة أخرى.'
}

export default function LoginPage() {
  const { user, login, loginWithGoogleCredential } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (user) return <Navigate to="/dashboard" replace />

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await login(email, password)
      const from = (location.state as { from?: string } | null)?.from
      navigate(from || '/dashboard', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const google = async (credential: string) => {
    setError('')
    try {
      await loginWithGoogleCredential(credential)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <main className="prototype-auth-page">
      <section className="prototype-auth-visual">
        <WeamLogo to="/" light />
        <div className="auth-scene">
          <img src="/prototype-girl.png" alt="طفلة ضمن الهوية البصرية لوئام" />
          <div className="auth-scene-copy">
            <span>مرحبًا بعودتك 💛</span>
            <h1>كل فريق الطفل في مساحة واحدة.</h1>
            <p>تابعي التقارير والأهداف والجلسات والتحديثات من نقطة واحدة.</p>
          </div>
        </div>
        <small>نسخة المسابقة تستخدم بيانات تجريبية فقط.</small>
      </section>

      <section className="prototype-auth-form-wrap">
        <div className="prototype-auth-form">
          <div className="mobile-logo"><WeamLogo compact /></div>
          <span className="soft-kicker">تسجيل الدخول</span>
          <h2>أهلًا بك في وئام</h2>
          <p className="muted auth-intro">أدخلي بيانات حسابك للمتابعة.</p>

          <form className="form-stack" onSubmit={submit}>
            <label>البريد الإلكتروني<input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@example.com" /></label>
            <label>كلمة المرور<input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" /></label>
            {error && <div className="alert alert-error">{error}</div>}
            <button className="btn btn-primary btn-block btn-large" disabled={submitting}>{submitting ? 'جاري الدخول...' : 'تسجيل الدخول'}</button>
          </form>

          <div className="divider"><span>أو</span></div>
          <GoogleSignInButton onCredential={google} />
          <p className="auth-switch">ما عندك حساب؟ <Link to="/register">إنشاء حساب جديد</Link></p>
          <Link className="back-home-link" to="/">العودة إلى البداية</Link>
        </div>
      </section>
    </main>
  )
}
