import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { ChildProfile, VoiceNote } from '../types'
import '../styles/voice-notes.css'

function formatDuration(seconds?: number | null) {
  if (!seconds) return '—'
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${String(secs).padStart(2, '0')}`
}

function providerLabel(note: VoiceNote) {
  if (note.transcription_status === 'completed') return 'تم تحويله إلى نص'
  if (note.transcription_status === 'failed') return 'تعذر تحويله إلى نص'
  return 'بانتظار التحويل إلى نص'
}

export default function VoiceNotesPage() {
  const { childId } = useParams()
  const [child, setChild] = useState<ChildProfile | null>(null)
  const [notes, setNotes] = useState<VoiceNote[]>([])
  const [title, setTitle] = useState('ملاحظة متابعة')
  const [recording, setRecording] = useState(false)
  const [recordedFile, setRecordedFile] = useState<File | null>(null)
  const [recordedUrl, setRecordedUrl] = useState<string | null>(null)
  const [duration, setDuration] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [audioUrls, setAudioUrls] = useState<Record<string, string>>({})
  const [drafts, setDrafts] = useState<Record<string, string>>({})

  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<number | null>(null)
  const startedAtRef = useRef<number>(0)

  const primary = child?.guardian_type === 'primary'
  const canCreate = Boolean(
    primary || child?.access_permissions.includes('create_voice_notes'),
  )

  const load = async () => {
    if (!childId) return
    const [childResponse, notesResponse] = await Promise.all([
      apiClient.get<ChildProfile>(`/children/${childId}`),
      apiClient.get<VoiceNote[]>(`/children/${childId}/voice-notes`),
    ])
    setChild(childResponse.data)
    setNotes(notesResponse.data)
  }

  useEffect(() => {
    load().catch(() =>
      setError(
        'تعذر فتح الملاحظات الصوتية أو لا توجد صلاحية للوصول إليها.',
      ),
    )
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current)
      Object.values(audioUrls).forEach((url) => URL.revokeObjectURL(url))
      if (recordedUrl) URL.revokeObjectURL(recordedUrl)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [childId])

  const startRecording = async () => {
    setError('')
    setNotice('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'
      const recorder = new MediaRecorder(stream, { mimeType })
      chunksRef.current = []

      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data)
      }

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType })
        const file = new File(
          [blob],
          `weam-voice-${Date.now()}.webm`,
          { type: recorder.mimeType },
        )
        if (recordedUrl) URL.revokeObjectURL(recordedUrl)
        setRecordedFile(file)
        setRecordedUrl(URL.createObjectURL(blob))
        stream.getTracks().forEach((track) => track.stop())
      }

      recorder.start()
      recorderRef.current = recorder
      startedAtRef.current = Date.now()
      setDuration(0)

      timerRef.current = window.setInterval(() => {
        setDuration(
          Math.max(
            0,
            Math.round((Date.now() - startedAtRef.current) / 1000),
          ),
        )
      }, 500)

      setRecording(true)
    } catch {
      setError(
        'لم يتم السماح باستخدام الميكروفون. فعّلي إذن الميكروفون للمتصفح.',
      )
    }
  }

  const stopRecording = () => {
    if (recorderRef.current?.state === 'recording') {
      recorderRef.current.stop()
    }
    if (timerRef.current) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
    setRecording(false)
  }

  const uploadAudio = async () => {
    if (!childId || !recordedFile) return

    const data = new FormData()
    data.append('title', title || 'ملاحظة صوتية')
    data.append('duration_seconds', String(duration))
    data.append('file', recordedFile)

    setBusy(true)
    setError('')
    setNotice('')

    try {
      await apiClient.post(`/children/${childId}/voice-notes`, data)
      setRecordedFile(null)
      if (recordedUrl) URL.revokeObjectURL(recordedUrl)
      setRecordedUrl(null)
      setDuration(0)
      setNotice('تم حفظ التسجيل. يمكنك الآن تفريغ الصوت إلى نص.')
      await load()
    } catch {
      setError(
        'تعذر رفع التسجيل. يدعم وئام WebM وWAV وMP3 وM4A حتى 25MB.',
      )
    } finally {
      setBusy(false)
    }
  }

  const uploadExisting = async (file?: File) => {
    if (!file || !childId) return
    const data = new FormData()
    data.append('title', title || file.name)
    data.append('file', file)

    setBusy(true)
    setError('')

    try {
      await apiClient.post(`/children/${childId}/voice-notes`, data)
      setNotice('تم رفع الملف الصوتي.')
      await load()
    } catch {
      setError('تعذر رفع الملف الصوتي.')
    } finally {
      setBusy(false)
    }
  }

  const transcribe = async (note: VoiceNote) => {
    setBusy(true)
    setError('')
    setNotice('')

    try {
      const response = await apiClient.post<VoiceNote>(
        `/voice-notes/${note.id}/transcribe`,
      )

      setDrafts((current) => ({
        ...current,
        [note.id]: response.data.transcript_draft ?? '',
      }))

      await load()

      if (response.data.transcription_status === 'failed') {
        setError(response.data.error_message || 'تعذر تفريغ التسجيل.')
      } else if (response.data.stt_provider === 'local_whisper') {
        setNotice(
          'تم تحويل التسجيل إلى نص. راجعيه قبل الاعتماد.',
        )
      } else {
        setNotice('تم إنشاء مسودة نص للمراجعة.')
      }
    } catch {
      setError('تعذر إنشاء التفريغ.')
    } finally {
      setBusy(false)
    }
  }

  const review = async (
    note: VoiceNote,
    reviewStatus: 'approved' | 'rejected',
  ) => {
    const transcript = drafts[note.id] ?? note.transcript_draft ?? ''
    if (!transcript.trim()) return

    setBusy(true)
    setError('')

    try {
      await apiClient.patch(`/voice-notes/${note.id}/review`, {
        review_status: reviewStatus,
        transcript,
      })
      await load()

      setNotice(
        reviewStatus === 'approved'
          ? 'تم اعتماد التفريغ بعد المراجعة البشرية.'
          : 'تم رفض مسودة التفريغ.',
      )
    } catch {
      setError('تعذر حفظ المراجعة.')
    } finally {
      setBusy(false)
    }
  }

  const loadAudio = async (note: VoiceNote) => {
    if (audioUrls[note.id]) return

    try {
      const response = await apiClient.get(
        `/voice-notes/${note.id}/audio`,
        { responseType: 'blob' },
      )
      setAudioUrls((current) => ({
        ...current,
        [note.id]: URL.createObjectURL(response.data),
      }))
    } catch {
      setError('تعذر تحميل التسجيل.')
    }
  }

  if (!child && !error) {
    return (
      <div className="loading-row">
        <div className="spinner" /> جاري تحميل الملاحظات الصوتية...
      </div>
    )
  }

  if (!child) {
    return (
      <div className="prototype-empty-card">
        <h2>تعذر فتح الملاحظات الصوتية</h2>
        <p>{error}</p>
        <Link className="btn btn-primary" to="/dashboard">
          الرئيسية
        </Link>
      </div>
    )
  }

  return (
    <section className="voice-page">
      <div className="voice-hero">
        <div>
          <Link to={`/children/${child.id}`} className="voice-back">
            ← العودة إلى ملف الطفل
          </Link>
          <span className="soft-kicker">الملاحظات الصوتية</span>
          <h1>ملاحظات {child.preferred_name || child.first_name} الصوتية</h1>
          <p>
            سجلي تحديثًا سريعًا، حوّليه إلى نص، ثم راجعي التفريغ قبل اعتماده
            ومشاركته مع الفريق.
          </p>
        </div>
        <span className="voice-human-badge">
          🎙 مراجعة بشرية قبل الاعتماد
        </span>
      </div>

      <div className="voice-dev-note">
        <strong>خصوصية الملاحظة الصوتية</strong>
        <p>
          تُحفظ الملاحظة بأمان، ولا يظهر النص لفريق الرعاية قبل مراجعته واعتماده.
        </p>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}

      {canCreate && (
        <div className="voice-recorder-card">
          <div className="voice-recorder-copy">
            <span className="voice-mic">●</span>
            <div>
              <h2>{recording ? 'جاري التسجيل...' : 'سجلي ملاحظة جديدة'}</h2>
              <p>
                مناسبة لتحديث سريع بعد جلسة، اجتماع أو ملاحظة من المنزل.
              </p>
            </div>
          </div>

          <label className="field">
            <span>عنوان الملاحظة</span>
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={180}
            />
          </label>

          <div className="voice-record-controls">
            <strong>{formatDuration(duration)}</strong>

            {!recording ? (
              <button
                className="btn btn-primary"
                onClick={() => void startRecording()}
              >
                🎙 بدء التسجيل
              </button>
            ) : (
              <button className="btn btn-white" onClick={stopRecording}>
                ■ إيقاف
              </button>
            )}

            <label className="btn btn-white voice-file-button">
              رفع ملف صوتي
              <input
                type="file"
                accept="audio/webm,audio/wav,audio/mpeg,audio/mp4,.m4a"
                onChange={(event) => {
                  void uploadExisting(event.target.files?.[0])
                  event.currentTarget.value = ''
                }}
              />
            </label>
          </div>

          {recordedUrl && (
            <div className="voice-preview">
              <audio controls src={recordedUrl} />
              <button
                className="btn btn-primary"
                disabled={busy}
                onClick={() => void uploadAudio()}
              >
                {busy ? 'جارٍ الحفظ...' : 'حفظ التسجيل'}
              </button>
            </div>
          )}
        </div>
      )}

      {!notes.length ? (
        <div className="prototype-empty-card">
          <span>🎙</span>
          <h2>لا توجد ملاحظات صوتية بعد</h2>
          <p>
            أول تسجيل سيظهر هنا مع الصوت، مسودة التفريغ، وحالة المراجعة.
          </p>
        </div>
      ) : (
        <div className="voice-note-list">
          {notes.map((note) => {
            const draftValue =
              drafts[note.id] ?? note.transcript_draft ?? ''

            return (
              <article className="voice-note-card" key={note.id}>
                <div className="voice-note-head">
                  <div>
                    <div className="voice-note-badges">
                      <span>
                        {note.review_status === 'approved'
                          ? 'معتمد بشريًا'
                          : note.review_status === 'draft'
                            ? 'مسودة للمراجعة'
                            : note.review_status === 'rejected'
                              ? 'مرفوض'
                              : 'بانتظار التفريغ'}
                      </span>
                      <span>{providerLabel(note)}</span>
                      <span>{formatDuration(note.duration_seconds)}</span>
                    </div>

                    <h2>{note.title}</h2>
                    <p>
                      بواسطة {note.created_by_name} ·{' '}
                      {new Date(note.created_at).toLocaleString(
                        'ar-SA-u-ca-gregory',
                      )}
                    </p>
                  </div>

                  <button
                    className="btn btn-white btn-small"
                    onClick={() => void loadAudio(note)}
                  >
                    تشغيل الصوت
                  </button>
                </div>

                {audioUrls[note.id] && (
                  <audio
                    className="voice-note-audio"
                    controls
                    src={audioUrls[note.id]}
                  />
                )}

                {note.transcription_status === 'not_started' && canCreate && (
                  <button
                    className="btn btn-primary"
                    disabled={busy}
                    onClick={() => void transcribe(note)}
                  >
                    ✦ تفريغ الصوت إلى نص
                  </button>
                )}

                {note.transcription_status === 'failed' && (
                  <div className="alert alert-error">
                    {note.error_message || 'فشل التفريغ.'}
                  </div>
                )}

                {note.review_status === 'draft' && canCreate && (
                  <div className="voice-review-box">
                    <label>
                      <span>راجعي التفريغ قبل الاعتماد</span>
                      <textarea
                        rows={5}
                        dir="auto"
                        value={draftValue}
                        onChange={(event) =>
                          setDrafts((current) => ({
                            ...current,
                            [note.id]: event.target.value,
                          }))
                        }
                      />
                    </label>

                    <div className="voice-review-actions">
                      <button
                        className="btn btn-white"
                        disabled={busy}
                        onClick={() => void review(note, 'rejected')}
                      >
                        رفض المسودة
                      </button>

                      <button
                        className="btn btn-primary"
                        disabled={busy}
                        onClick={() => void review(note, 'approved')}
                      >
                        اعتماد التفريغ
                      </button>
                    </div>
                  </div>
                )}

                {note.review_status === 'approved' &&
                  note.transcript_final && (
                    <div className="voice-approved-transcript">
                      <span>النص المعتمد</span>
                      <p dir="auto">{note.transcript_final}</p>
                      <small>
                        اعتمد بواسطة{' '}
                        {note.reviewed_by_name || 'عضو مخول'}
                      </small>
                    </div>
                  )}

                {note.review_status === 'draft' && !canCreate && (
                  <div className="voice-private-draft">
                    المسودة بانتظار مراجعة عضو مخول، ولن تظهر لك قبل
                    اعتمادها.
                  </div>
                )}
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}
