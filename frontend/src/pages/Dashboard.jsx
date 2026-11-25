import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'

function Metric({ label, value, note, tone = 'blue' }) {
  return <div className={`dashboard-metric accent-${tone}`}><span className="dashboard-metric-label">{label}</span><strong className="dashboard-metric-value">{value}</strong><span className="dashboard-metric-note">{note}</span></div>
}

function scoreTone(score) {
  return score >= 0.8 ? 'mastered' : score >= 0.6 ? 'on-track' : score >= 0.4 ? 'needs-focus' : 'at-risk'
}

function ActivityChart({ daily = [] }) {
  const max = Math.max(1, ...daily.map((item) => item.count))
  return <div className="activity-chart" role="img" aria-label="Your learning activity over the last seven days">{daily.map((item) => <div className="activity-column" key={item.date}><span className="activity-count">{item.count}</span><div className="activity-track"><span style={{ height: `${Math.max(4, item.count / max * 100)}%` }} /></div><small>{new Date(`${item.date}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short' })}</small></div>)}</div>
}

export default function Dashboard() {
  const [plan, setPlan] = useState([])
  const [trends, setTrends] = useState({ overall_mastery: 0, trends: [] })
  const [activity, setActivity] = useState(null)
  const [courses, setCourses] = useState([])
  const [assessments, setAssessments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api.getStudyPlan().catch(() => []),
      api.progressTrends().catch(() => ({ overall_mastery: 0, trends: [] })),
      api.progressActivity().catch(() => null),
      api.listCourses()
        .then((rows) => Promise.all(rows.map((course) => api.getCourse(course.id).catch(() => course))))
        .catch(() => []),
      api.myAssessments().catch(() => []),
    ]).then(([studyPlan, mastery, activityData, courseRows, assessmentRows]) => {
      if (cancelled) return
      setPlan(studyPlan)
      setTrends(mastery)
      setActivity(activityData)
      setCourses(courseRows)
      setAssessments(assessmentRows)
    }).catch(() => !cancelled && setError('Your learning dashboard could not be loaded.'))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [])

  if (loading) return <div className="dashboard-content">Loading your learning overview...</div>

  const focusTopics = trends.trends.filter((topic) => topic.score < 0.7)
  const weekly = activity?.weekly || {}
  const nextSteps = [...plan].sort((a, b) => a.scheduled_order - b.scheduled_order).slice(0, 3)
  const firstAssessment = assessments[0]
  const subjects = courses.map((course) => {
    const scores = (course.topics || [])
      .map((topic) => trends.trends.find((trend) => trend.topic_id === topic.id)?.score)
      .filter((score) => score != null)
    return {
      ...course,
      mastery: scores.length ? scores.reduce((sum, score) => sum + score, 0) / scores.length : null,
    }
  })

  return (
    <div className="dashboard-content student-dashboard">
      <div className="dashboard-heading">
        <div><div className="dashboard-eyebrow">Learning intelligence / Student</div><h1>My learning dashboard</h1><p>{courses[0]?.title || 'Your approved syllabus'} · Personal learning overview</p></div>
        <div className="dashboard-date">This week <span className="breadcrumb-divider">/</span> All time</div>
      </div>
      {error && <p className="mb-4 text-sm text-[var(--color-rust)]" role="alert">{error}</p>}

      <section className="dashboard-metrics" aria-label="Student learning KPIs">
        <Metric label="Overall mastery" value={`${Math.round((trends.overall_mastery || 0) * 100)}%`} note="Across assessed topics" tone="green" />
        <Metric label="Learning steps" value={plan.length} note="Recommended in your personal plan" />
        <Metric label="Practice attempts" value={weekly.quiz_count ?? 0} note="Quiz and diagnostic attempts this week" tone="amber" />
        <Metric label="Topics needing focus" value={focusTopics.length} note="Start with your weakest concept" tone="red" />
      </section>

      <div className="dashboard-columns student-dashboard-columns">
        <section className="dashboard-panel">
          <div className="dashboard-panel-header"><div><h2>My subjects</h2><p>Select a subject to open its topic path.</p></div><Link to="/learning-path" className="dashboard-panel-link">Open learning path</Link></div>
          {subjects.length ? <div className="student-subject-list">{subjects.map((course) => <Link className="student-subject-row" key={course.id} to={`/learning-path?course=${course.id}`}><span className="student-subject-heading"><strong>{course.title}</strong><span className={course.mastery == null ? 'not-started' : scoreTone(course.mastery)}>{course.mastery == null ? 'No quiz scores yet' : `${Math.round(course.mastery * 100)}%`}</span></span><span className="student-subject-track" role="progressbar" aria-label={`${course.title} mastery`} aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round((course.mastery || 0) * 100)}><span className={course.mastery == null ? 'not-started' : scoreTone(course.mastery)} style={{ width: `${Math.round((course.mastery || 0) * 100)}%` }} /></span></Link>)}</div> : <div className="dashboard-empty"><p>No class joined yet. Enter a faculty join code or upload a syllabus to build a learning path.</p><Link to="/courses" className="btn-primary px-4 py-2 text-sm">Browse courses</Link><Link to="/upload" className="dashboard-panel-link">Upload my syllabus</Link></div>}
        </section>

        <section className="dashboard-panel">
          <div className="dashboard-panel-header"><div><h2>My next learning steps</h2><p>Recommended in priority order.</p></div><Link to="/learning-path" className="dashboard-panel-link">Full path</Link></div>
          {nextSteps.length ? <div className="next-step-list">{nextSteps.map((item, index) => <div className="next-step" key={item.id}><span className="next-step-number">{index + 1}</span><span className="next-step-copy"><strong>{item.topic_title}</strong><small>{item.reason || item.status.replaceAll('_', ' ')}</small></span><Link className="next-step-action" to={`/study/${item.topic_id}?title=${encodeURIComponent(item.topic_title)}`}>Learn</Link></div>)}</div> : <div className="dashboard-empty"><p>Your path appears after a syllabus is ready.</p><Link to="/upload" className="btn-primary px-4 py-2 text-sm">Add syllabus</Link></div>}
        </section>

      </div>

      <section className={`student-assessment-banner${firstAssessment ? '' : ' is-empty'}`} aria-label="Upcoming assessment"><div><strong>{firstAssessment ? `Upcoming: ${firstAssessment.title}` : 'Upcoming assessments'}</strong><p>{firstAssessment ? <>{firstAssessment.topic_title || 'Course assessment'} <span aria-hidden="true">·</span> {firstAssessment.duration_minutes} minutes <span aria-hidden="true">·</span> {firstAssessment.scheduled_at ? `Due ${new Date(firstAssessment.scheduled_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}` : 'Schedule pending'} <span aria-hidden="true">·</span> AI support {firstAssessment.ai_support_enabled ? 'permitted' : 'disabled'}</> : 'No faculty-scheduled assessments are available yet.'}</p></div><Link to="/tests" className="dashboard-panel-link">View tests</Link></section>

      <section className="dashboard-panel student-activity-panel">
        <div className="dashboard-panel-header"><div><h2>My learning activity</h2><p>Recorded learning activity over the last seven days.</p></div><span className="status-pill on-track">{weekly.active_days ?? 0} active days</span></div>
        <ActivityChart daily={activity?.daily_activity} />
      </section>
    </div>
  )
}
