import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { ChildReport, ReportAIAnalysis, ReportAIResult } from '../types'
import '../styles/ai-reports.css'

const EMPTY_RESULT: ReportAIResult = {
  summary: '',
  key_findings: [],
  needs: [],
  recommendations: [],
  follow_up_actions: [],
  goal_mentions: [],
  source_language: 'unknown',
  evidence: [],
  limitations: [],
  safety_note: '',
}

function listText(items?: string[]) {
  return (items ?? []).join('\n')
}

function parseList(value: string) {
  return value.split('\n').map((item) => item.trim()).filter(Boolean)
}

function textDirection(value?: string | null): 'rtl' | 'ltr' {
  if (!value) return 'rtl'
  const arabicCharacters = (value.match(/[\u0600-\u06FF]/g) ?? []).length
  const latinCharacters = (value.match(/[A-Za-z]/g) ?? []).length
  return latinCharacters > arabicCharacters ? 'ltr' : 'rtl'
}

function AnalysisList({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="ai-result-section">
      <h3>{title}</h3>
      {items.length ? (
        <ul>
          {items.map((item, index) => (
            <li
              key={`${item}-${index}`}
              dir={textDirection(item)}
              className={textDirection(item) === 'ltr' ? 'ai-ltr-content' : undefined}
            >
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">لم يستخرج النظام عناصر مؤكدة في هذا القسم.</p>
      )}
    </section>
  )
}


function providerDisplay(provider: string, model: string) {
  if (provider === 'gemini' && model === 'gemini-3.6-flash') {
    return 'Gemini 3.6 · النموذج الأساسي'
  }
  if (provider === 'gemini' && model === 'gemini-3.5-flash') {
    return 'Gemini 3.5 · النموذج الاحتياطي'
  }
  if (provider === 'local_fallback' || provider === 'mock') {
    return 'تحليل محلي · احتياطي'
  }
  return `${provider} · ${model}`
}


export default function ReportAIPage() {
  const { reportId } = useParams()
  const [report, setReport] = useState<ChildReport | null>(null)
  const [analyses, setAnalyses] = useState<ReportAIAnalysis[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reviewingId, setReviewingId] = useState<string | null>(null)
  const [draft, setDraft] = useState<ReportAIResult>(EMPTY_RESULT)

  const latest = analyses[0]
  const canGenerate = Boolean(report)

  const load = async () => {
    if (!reportId) return
    const [reportResponse, analysesResponse] = await Promise.all([
      apiClient.get<ChildReport>(`/reports/${reportId}`),
      apiClient.get<ReportAIAnalysis[]>(`/reports/${reportId}/ai-analyses`),
    ])
    setReport(reportResponse.data)
    setAnalyses(analysesResponse.data)
  }

  useEffect(() => {
    if (!reportId) return
    setLoading(true)
    setError('')
    load()
      .catch(() => setError('تعذر فتح تحليل التقرير أو لا توجد صلاحية للوصول إليه.'))
      .finally(() => setLoading(false))
  }, [reportId])

  const runAnalysis = async () => {
    if (!reportId) return
    setRunning(true)
    setError('')
    setNotice('')
    try {
      const response = await apiClient.post<ReportAIAnalysis>(
        `/reports/${reportId}/ai-analyses`,
        {},
      )
      await load()
      if (response.data.analysis_status === 'failed') {
        setError(response.data.error_message || 'تعذر إكمال التحليل.')
      } else {
        setNotice('اكتمل التحليل كمسودة. راجعي المحتوى قبل اعتماده.')
      }
    } catch {
      setError('تعذر تشغيل التحليل. تحققي من الصلاحية وإعدادات مزود الذكاء الاصطناعي.')
    } finally {
      setRunning(false)
    }
  }

  const startReview = (analysis: ReportAIAnalysis) => {
    setReviewingId(analysis.id)
    setDraft({
      ...EMPTY_RESULT,
      ...analysis.result,
      key_findings: [...(analysis.result.key_findings ?? [])],
      needs: [...(analysis.result.needs ?? [])],
      recommendations: [...(analysis.result.recommendations ?? [])],
      follow_up_actions: [...(analysis.result.follow_up_actions ?? [])],
      goal_mentions: [...(analysis.result.goal_mentions ?? [])],
      evidence: [...(analysis.result.evidence ?? [])],
      limitations: [...(analysis.result.limitations ?? [])],
    })
  }

  const saveReview = async (
    analysis: ReportAIAnalysis,
    reviewStatus: 'approved' | 'rejected',
  ) => {
    setError('')
    setNotice('')
    try {
      await apiClient.patch(`/report-ai-analyses/${analysis.id}/review`, {
        review_status: reviewStatus,
        edited_result: draft,
      })
      setReviewingId(null)
      await load()
      setNotice(
        reviewStatus === 'approved'
          ? 'تم اعتماد التحليل بعد المراجعة البشرية.'
          : 'تم رفض المسودة ولن تعامل كمعلومة معتمدة.',
      )
    } catch {
      setError('تعذر حفظ المراجعة.')
    }
  }

  const providerLabel = useMemo(() => {
    if (!latest) return ''
    return providerDisplay(latest.provider, latest.model)
  }, [latest])

  if (loading) {
    return <div className="loading-row"><div className="spinner" /> جاري تحميل التحليل...</div>
  }

  if (error && !report) {
    return (
      <div className="prototype-empty-card">
        <h2>تعذر فتح التحليل</h2>
        <p>{error}</p>
        <Link className="btn btn-primary" to="/dashboard">العودة للرئيسية</Link>
      </div>
    )
  }

  if (!report) return null

  return (
    <section className="ai-report-page">
      <div className="ai-report-hero">
        <div>
          <Link className="ai-report-back" to={`/children/${report.child_id}/reports`}>
            ← العودة للتقارير
          </Link>
          <span className="soft-kicker">تحليل التقرير بالذكاء الاصطناعي</span>
          <h1>فهم أسرع لـ {report.title}</h1>
          <p>
            وئام يستخرج أهم المعلومات من التقرير ويحولها إلى مسودة منظمة.
            لا يتم اعتماد أي نتيجة مهمة قبل مراجعة بشرية.
          </p>
        </div>

        <div className="ai-report-hero-actions">
          <span className="ai-draft-badge">✦ مراجعة بشرية قبل الاعتماد</span>
          {canGenerate && (
            <button
              className="btn btn-primary"
              onClick={() => void runAnalysis()}
              disabled={running}
            >
              {running ? 'جارٍ التحليل...' : '✦ تحليل أحدث نسخة'}
            </button>
          )}
        </div>
      </div>

      <div className="ai-safety-banner">
        <span>🛡️</span>
        <div>
          <strong>مساعد وليس تشخيصًا</strong>
          <p>
            التحليل يستخرج ما ورد في التقرير فقط، ولا يضيف تشخيصًا أو دواءً
            أو تغييرًا على الخطة العلاجية.
          </p>
        </div>
      </div>

      {(latest?.provider === 'local_fallback' || latest?.provider === 'mock') && (
        <div className="ai-development-banner">
          <span>ℹ</span>
          <div>
            <strong>
              {latest.provider === 'local_fallback'
                ? 'تم استخدام التحليل المحلي الاحتياطي'
                : 'وضع التطوير المحلي'}
            </strong>
            <p>
              {latest.provider === 'local_fallback'
                ? 'تعذر استخدام نماذج Gemini مؤقتًا، لذلك أكمل وئام التحليل محليًا. يمكنك إعادة التحليل لاحقًا، وسيجرب Gemini 3.6 تلقائيًا من جديد.'
                : 'هذه النتيجة محلية ومخصصة لاختبار سير العمل.'}
            </p>
          </div>
        </div>
      )}

      {notice && <div className="alert alert-success">{notice}</div>}
      {error && <div className="alert alert-error">{error}</div>}

      {!analyses.length ? (
        <div className="prototype-empty-card">
          <span>✦</span>
          <h2>لم يتم تحليل هذا التقرير بعد</h2>
          <p>ابدئي بتحليل أحدث نسخة، ثم راجعي الملخص والنتائج قبل اعتمادها.</p>
          <button
            className="btn btn-primary"
            onClick={() => void runAnalysis()}
            disabled={running}
          >
            {running ? 'جارٍ التحليل...' : 'بدء التحليل'}
          </button>
        </div>
      ) : (
        <div className="ai-analysis-list">
          {analyses.map((analysis, index) => {
            const isReviewing = reviewingId === analysis.id
            const result = analysis.result ?? EMPTY_RESULT
            const summaryDirection = textDirection(result.summary)

            return (
              <article
                className={`ai-analysis-card ${analysis.review_status}`}
                key={analysis.id}
              >
                <div className="ai-analysis-head">
                  <div>
                    <div className="ai-analysis-badges">
                      <span>v{analysis.report_version_number}</span>
                      <span>
                        {analysis.analysis_status === 'completed'
                          ? 'اكتمل التحليل'
                          : 'فشل التحليل'}
                      </span>
                      <span className={`review ${analysis.review_status}`}>
                        {analysis.review_status === 'approved'
                          ? 'معتمد بشريًا'
                          : analysis.review_status === 'rejected'
                            ? 'مرفوض'
                            : 'مسودة للمراجعة'}
                      </span>
                    </div>
                    <h2>
                      {index === 0
                        ? 'أحدث تحليل'
                        : `تحليل سابق ${analyses.length - index}`}
                    </h2>
                    <p>
                      {providerDisplay(analysis.provider, analysis.model)}
                      {' · '}بواسطة {analysis.created_by_name}
                    </p>
                  </div>
                  <time>
                    {new Date(analysis.created_at).toLocaleString(
                      'ar-SA-u-ca-gregory',
                    )}
                  </time>
                </div>

                {analysis.analysis_status === 'failed' ? (
                  <div className="ai-failed-box">
                    <strong>لم يكتمل التحليل</strong>
                    <p>{analysis.error_message}</p>
                  </div>
                ) : isReviewing ? (
                  <div className="ai-review-editor">
                    <h3>مراجعة وتحرير المسودة</h3>

                    <label>
                      <span>الملخص</span>
                      <textarea
                        dir="auto"
                        rows={4}
                        value={draft.summary}
                        onChange={(event) =>
                          setDraft({ ...draft, summary: event.target.value })
                        }
                      />
                    </label>

                    <div className="ai-review-grid">
                      <label>
                        <span>أهم النتائج — كل سطر عنصر</span>
                        <textarea
                          dir="auto"
                          rows={6}
                          value={listText(draft.key_findings)}
                          onChange={(event) =>
                            setDraft({
                              ...draft,
                              key_findings: parseList(event.target.value),
                            })
                          }
                        />
                      </label>

                      <label>
                        <span>الاحتياجات — كل سطر عنصر</span>
                        <textarea
                          dir="auto"
                          rows={6}
                          value={listText(draft.needs)}
                          onChange={(event) =>
                            setDraft({
                              ...draft,
                              needs: parseList(event.target.value),
                            })
                          }
                        />
                      </label>

                      <label>
                        <span>التوصيات المذكورة في التقرير</span>
                        <textarea
                          dir="auto"
                          rows={6}
                          value={listText(draft.recommendations)}
                          onChange={(event) =>
                            setDraft({
                              ...draft,
                              recommendations: parseList(event.target.value),
                            })
                          }
                        />
                      </label>

                      <label>
                        <span>إجراءات المتابعة</span>
                        <textarea
                          dir="auto"
                          rows={6}
                          value={listText(draft.follow_up_actions)}
                          onChange={(event) =>
                            setDraft({
                              ...draft,
                              follow_up_actions: parseList(event.target.value),
                            })
                          }
                        />
                      </label>
                    </div>

                    <div className="ai-review-actions">
                      <button
                        className="btn btn-white"
                        onClick={() => setReviewingId(null)}
                      >
                        إلغاء
                      </button>
                      <button
                        className="btn btn-white"
                        onClick={() => void saveReview(analysis, 'rejected')}
                      >
                        رفض المسودة
                      </button>
                      <button
                        className="btn btn-primary"
                        onClick={() => void saveReview(analysis, 'approved')}
                      >
                        اعتماد بعد المراجعة
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <section className="ai-summary-box">
                      <span>الملخص</span>
                      <p
                        dir={summaryDirection}
                        className={
                          summaryDirection === 'ltr'
                            ? 'ai-ltr-content'
                            : undefined
                        }
                      >
                        {result.summary || 'لم يتوفر ملخص.'}
                      </p>
                    </section>

                    <div className="ai-result-grid">
                      <AnalysisList
                        title="أهم النتائج"
                        items={result.key_findings ?? []}
                      />
                      <AnalysisList
                        title="الاحتياجات"
                        items={result.needs ?? []}
                      />
                      <AnalysisList
                        title="التوصيات المذكورة"
                        items={result.recommendations ?? []}
                      />
                      <AnalysisList
                        title="إجراءات المتابعة"
                        items={result.follow_up_actions ?? []}
                      />
                    </div>

                    {!!result.evidence?.length && (
                      <AnalysisList
                        title="أدلة قصيرة من المصدر"
                        items={result.evidence}
                      />
                    )}

                    {!!result.limitations?.length && (
                      <AnalysisList
                        title="حدود التحليل"
                        items={result.limitations}
                      />
                    )}

                    <div className="ai-safety-note">{result.safety_note}</div>

                    {analysis.review_status === 'draft' && (
                      <div className="ai-card-actions">
                        <button
                          className="btn btn-primary"
                          onClick={() => startReview(analysis)}
                        >
                          مراجعة وتحرير
                        </button>
                      </div>
                    )}

                    {analysis.review_status !== 'draft' && (
                      <div className="ai-reviewed-by">
                        {analysis.review_status === 'approved' ? '✓ اعتمد' : '× رُفض'}
                        {' '}بواسطة {analysis.reviewed_by_name || 'عضو مخول'}
                      </div>
                    )}
                  </>
                )}
              </article>
            )
          })}
        </div>
      )}

      {providerLabel && (
        <div className="ai-provider-note">المزود الحالي: {providerLabel}</div>
      )}
    </section>
  )
}
