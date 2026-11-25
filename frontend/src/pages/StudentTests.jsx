import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'

export default function StudentTests() {
  const [assessments, setAssessments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    api.myAssessments()
      .then((rows) => !cancelled && setAssessments(rows))
      .catch(() => !cancelled && setError('Scheduled tests could not be loaded.'))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [])

  if (loading) return <div className="dashboard-content">Loading scheduled tests...</div>
  return (
    <div className="dashboard-content">
      <div className="dashboard-heading"><div><div className="dashboard-eyebrow">Student / Tests</div><h1>My tests</h1><p>Faculty-scheduled assessments for your enrolled classes.</p></div><Link to="/learning-path" className="btn-secondary px-3 py-2 text-sm">My learning path</Link></div>
      {error && <p className="mb-4 text-sm text-[var(--color-rust)]" role="alert">{error}</p>}
      {assessments.length ? <div className="dashboard-stack">{assessments.map((assessment) => {
        const startsAt = assessment.scheduled_at ? new Date(assessment.scheduled_at) : null
        const now = new Date()
        const ended = startsAt && now > new Date(startsAt.getTime() + assessment.duration_minutes * 60000)
        const upcoming = startsAt && now < startsAt
        return <article className="assessment-card" key={assessment.id}><div className="assessment-date-block"><strong>{startsAt ? startsAt.toLocaleDateString(undefined, { day: '2-digit' }) : '--'}</strong><span>{startsAt ? startsAt.toLocaleDateString(undefined, { month: 'short' }) : 'Draft'}</span></div><div className="assessment-card-copy"><div className="dashboard-eyebrow">{assessment.topic_title}</div><h2>{assessment.title}</h2><p>{startsAt ? startsAt.toLocaleString() : 'Schedule pending'} <span>·</span> {assessment.duration_minutes} minutes</p><p className={assessment.ai_support_enabled ? 'text-[var(--color-forest)]' : 'text-[var(--color-rust)]'}>AI support {assessment.ai_support_enabled ? 'enabled' : 'disabled during this test'}</p></div><div className="assessment-card-action">{ended ? <span className="badge-review px-2 py-1 text-xs">Window closed</span> : upcoming ? <span className="badge-pending px-2 py-1 text-xs">Scheduled</span> : <Link className="btn-primary px-4 py-2 text-sm" to={`/assessment/${assessment.id}`}>Start test</Link>}</div></article>
      })}</div> : <section className="dashboard-panel dashboard-empty"><p>No faculty-scheduled tests are currently available.</p><Link to="/learning-path" className="dashboard-panel-link">Continue learning path</Link></section>}
    </div>
  )
}
