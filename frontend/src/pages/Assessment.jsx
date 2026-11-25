import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../lib/api'

function formatTime(seconds) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, '0')
  const remainder = (seconds % 60).toString().padStart(2, '0')
  return `${minutes}:${remainder}`
}

export default function Assessment() {
  const { assessmentId } = useParams()
  const [attempt, setAttempt] = useState(null)
  const [answers, setAnswers] = useState({})
  const [result, setResult] = useState(null)
  const [secondsLeft, setSecondsLeft] = useState(0)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    api.startAssessment(assessmentId)
      .then((data) => {
        if (cancelled) return
        setAttempt(data)
        setSecondsLeft(Math.max(0, Math.floor((new Date(data.ends_at).getTime() - Date.now()) / 1000)))
      })
      .catch((requestError) => !cancelled && setError(requestError.message || 'This assessment could not be started.'))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [assessmentId])

  useEffect(() => {
    if (!attempt || result || secondsLeft <= 0) return undefined
    const timer = setInterval(() => {
      const remaining = Math.max(0, Math.floor((new Date(attempt.ends_at).getTime() - Date.now()) / 1000))
      setSecondsLeft(remaining)
    }, 1000)
    return () => clearInterval(timer)
  }, [attempt, result, secondsLeft])

  async function submit(event) {
    event?.preventDefault()
    if (!attempt || submitting || result || secondsLeft <= 0) return
    if (attempt.questions.some((_, index) => answers[index] === undefined)) {
      setError('Answer each question before submitting the assessment.')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const orderedAnswers = attempt.questions.map((_, index) => answers[index])
      const score = await api.submitQuiz(attempt.quiz_id, orderedAnswers)
      setResult(score)
    } catch (requestError) {
      setError(requestError.message || 'Your assessment could not be submitted.')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <div className="dashboard-content">Preparing your scheduled assessment...</div>
  if (error && !attempt) return <div className="dashboard-content"><div className="dashboard-panel p-6"><p className="text-[var(--color-rust)]">{error}</p><Link to="/tests" className="dashboard-panel-link">Back to tests</Link></div></div>

  return (
    <div className="dashboard-content assessment-page">
      <div className="dashboard-heading"><div><div className="dashboard-eyebrow">Scheduled assessment / {attempt.topic_title}</div><h1>{attempt.title}</h1><p>{attempt.questions.length} questions · {attempt.duration_minutes} minutes</p></div><div className={`timer-display ${secondsLeft < 300 ? 'timer-warning' : ''}`} aria-live="polite">{result ? 'Submitted' : formatTime(secondsLeft)}</div></div>
      <div className={`assessment-policy ${attempt.ai_support_enabled ? 'policy-allowed' : 'policy-blocked'}`}>{attempt.ai_support_enabled ? 'Faculty permits AI assistance during this assessment.' : 'AI assistance is disabled for this scheduled assessment.'}</div>
      {result ? <section className="dashboard-panel result-panel"><div className="dashboard-eyebrow">Assessment complete</div><h2>{Math.round(result.score * 100)}%</h2><p>{result.passed ? 'Meets the topic mastery threshold.' : 'Review the topic and continue with targeted practice.'}</p><Link to="/progress" className="btn-primary inline-block px-4 py-2">View progress</Link></section> : secondsLeft <= 0 ? <section className="dashboard-panel result-panel"><h2>Assessment time ended</h2><p>Your answers could not be submitted after the scheduled window closed.</p><Link to="/tests" className="btn-secondary inline-block px-4 py-2">Back to tests</Link></section> : <form onSubmit={submit} className="dashboard-stack">{attempt.questions.map((question, index) => <section className="dashboard-panel assessment-question" key={index}><div className="dashboard-eyebrow">Question {String(index + 1).padStart(2, '0')}</div><h2>{question.question}</h2><div className="answer-options">{question.options.map((option, optionIndex) => <label className={`answer-option${answers[index] === optionIndex ? ' selected' : ''}`} key={optionIndex}><input type="radio" name={`question-${index}`} checked={answers[index] === optionIndex} onChange={() => setAnswers((current) => ({ ...current, [index]: optionIndex }))} /><span>{option}</span></label>)}</div></section>)}{error && <p className="text-sm text-[var(--color-rust)]" role="alert">{error}</p>}<button type="submit" className="btn-primary px-5 py-3" disabled={submitting || secondsLeft <= 0}>{submitting ? 'Submitting...' : 'Submit assessment'}</button></form>}
    </div>
  )
}
