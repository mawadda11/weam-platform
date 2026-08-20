import { Link, Navigate } from 'react-router-dom'
import WeamLogo from '../components/WeamLogo'
import { useAuth } from '../contexts/AuthContext'

export default function HomePage() {
  const { user, loading } = useAuth()
  if (!loading && user) return <Navigate to="/dashboard" replace />

  return (
    <main className="welcome-page">
      <div className="sky-bubble bubble-one" />
      <div className="sky-bubble bubble-two" />
      <span className="butterfly butterfly-one">✦</span>
      <span className="butterfly butterfly-two">✦</span>

      <header className="welcome-nav">
        <WeamLogo to="/" compact />
        <div className="welcome-nav-actions">
          <Link className="btn btn-outline" to="/login">تسجيل الدخول</Link>
          <Link className="btn btn-primary" to="/register">إنشاء حساب</Link>
        </div>
      </header>

      <section className="welcome-hero">
        <div className="welcome-copy">
          <span className="soft-kicker">منصة واحدة لفريق الطفل كله</span>
          <WeamLogo />
          <h1>رحلة طفلك تستحق أن تُرى <span>كاملة.</span></h1>
          <p>
            تجمع وئام الأسرة والمختصين والمعلمين والمراكز حول سجل رعاية موحد،
            حتى تصل المعلومة الصحيحة للشخص الصحيح في الوقت المناسب.
          </p>
          <div className="welcome-actions">
            <Link className="btn btn-primary btn-large" to="/login">تسجيل الدخول</Link>
            <Link className="btn btn-white btn-large" to="/register">إنشاء حساب جديد</Link>
          </div>
          <div className="privacy-pill">🛡️ بيانات آمنة ومحمية • ولي الأمر يتحكم بالصلاحيات</div>
        </div>

        <div className="welcome-art" aria-label="واجهة مستوحاة من بروتوتايب وئام">
          <div className="scene-frame">
            <img src="/prototype-girl.png" alt="طفلة ضمن الهوية البصرية لبروتوتايب وئام" />
            <div className="scene-wash" />
            <div className="scene-copy">
              <span>كل يوم خطوة جديدة نحو</span>
              <strong>تطوير طفلك وتمكينه 💛</strong>
            </div>
            <div className="scene-card scene-card-one">👩‍⚕️ <b>المختص</b></div>
            <div className="scene-card scene-card-two">🏫 <b>المعلم</b></div>
            <div className="scene-card scene-card-three">👨‍👩‍👧 <b>الأسرة</b></div>
          </div>
        </div>
      </section>

      <section className="welcome-benefits">
        <article><span>📄</span><strong>تقارير موحدة</strong><small>كل تحديث في مكان واحد</small></article>
        <article><span>🎯</span><strong>أهداف واضحة</strong><small>متابعة تقدم الطفل باستمرار</small></article>
        <article><span>👥</span><strong>فريق مترابط</strong><small>بصلاحيات يتحكم بها ولي الأمر</small></article>
      </section>
    </main>
  )
}
