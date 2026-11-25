import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'

function tone(score) {
  return score >= 0.8 ? 'mastered' : score >= 0.6 ? 'on-track' : score >= 0.4 ? 'needs-focus' : 'at-risk'
}

function Metric({ label, value, note, color = 'blue' }) {
  return <div className={`dashboard-metric accent-${color}`}><span className="dashboard-metric-label">{label}</span><strong className="dashboard-metric-value">{value}</strong><span className="dashboard-metric-note">{note}</span></div>
}

export default function Progress() {
  const [data, setData] = useState(null)
  const [activity, setActivity] = useState(null)
  const [assessments, setAssessments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    Promise.all([api.progressTrends(), api.progressActivity(), api.myAssessments()])
      .then(([trends, activityData, testRows]) => {
        if (cancelled) return
        setData(trends)
        setActivity(activityData)
        setAssessments(testRows)
      })
      .catch(() => !cancelled && setError('Progress data could not be loaded.'))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [])

  if (loading) return <div className="dashboard-content">Loading your progress...</div>
  const topics = [...(data?.trends || [])].sort((a, b) => a.score - b.score)
  const weak = topics.filter((topic) => topic.score < 0.7)
  const weekly = activity?.weekly || {}

  return (
    <div className="dashboard-content">
      <div className="dashboard-heading"><div><div className="dashboard-eyebrow">Student / Progress</div><h1>My progress and mastery</h1><p>Strengths, focus areas, and learning activity over time.</p></div><span className="dashboard-date">Activity: last 7 days · Mastery: all time</span></div>
      {error && <p className="mb-4 text-sm text-[var(--color-rust)]" role="alert">{error}</p>}
      <section className="dashboard-metrics" aria-label="Progress metrics"><Metric label="Overall mastery" value={`${Math.round((data?.overall_mastery || 0) * 100)}%`} note="Across assessed topics" color="green" /><Metric label="Practice completion" value={weekly.quiz_count ?? 0} note="Quiz attempts in the last 7 days" /><Metric label="Test average" value={weekly.average_quiz_score == null ? '--' : `${Math.round(weekly.average_quiz_score * 100)}%`} note="Scored assessments this week" color="green" /><Metric label="Topics needing work" value={weak.length} note="Below the 70% study target" color="red" /></section>

      <div className="dashboard-columns">
        <section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Strengths and focus areas</h2><p>Mastery updates after completed topic quizzes.</p></div><Link to="/learning-path" className="dashboard-panel-link">Open learning path</Link></div>{topics.length ? <div className="topic-list">{topics.map((topic) => <div className="topic-row" key={topic.topic_id}><span className="topic-row-title">{topic.topic_title}</span><span className="topic-row-meta">{topic.attempts} attempt{topic.attempts === 1 ? '' : 's'} · {Math.round(topic.score * 100)}% <span className={`status-pill ${tone(topic.score)}`}>{topic.score >= 0.8 ? 'Mastered' : topic.score >= 0.6 ? 'On track' : topic.score >= 0.4 ? 'Needs focus' : 'At risk'}</span></span><div className="topic-progress-track"><div className={`topic-progress-fill ${tone(topic.score)}`} style={{ width: `${Math.round(topic.score * 100)}%` }} /></div></div>)}</div> : <div className="dashboard-empty"><p>Complete a quiz to begin tracking topic mastery.</p></div>}</section>
        <section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>My improvement trend</h2><p>Activity counts by day, last seven days.</p></div><span className="status-pill on-track">{weekly.active_days ?? 0} active days</span></div><div className="activity-chart" role="img" aria-label="Daily learning activity">{(activity?.daily_activity || []).map((day) => {const highest=Math.max(1,...(activity?.daily_activity||[]).map((item)=>item.count));return <div className="activity-column" key={day.date}><span className="activity-count">{day.count}</span><div className="activity-track"><span style={{height:`${Math.max(4,day.count/highest*100)}%`}} /></div><small>{new Date(`${day.date}T12:00:00`).toLocaleDateString(undefined,{weekday:'short'})}</small></div>})}</div><div className="dashboard-empty compact-empty"><p>Charts show recorded learning activity; no mastery history is inferred for days without a quiz.</p></div></section>
        <section className="dashboard-panel dashboard-panel-wide"><div className="dashboard-panel-header"><div><h2>Upcoming tests</h2><p>Faculty-scheduled assessments and support boundaries.</p></div><Link to="/tests" className="dashboard-panel-link">View all</Link></div>{assessments.length ? <div className="next-step-list">{assessments.slice(0,4).map((assessment)=><div className="next-step" key={assessment.id}><span className="next-step-number">{assessment.duration_minutes}</span><span className="next-step-copy"><strong>{assessment.title}</strong><small>{assessment.topic_title} · {assessment.scheduled_at?new Date(assessment.scheduled_at).toLocaleString():'Schedule pending'} · AI {assessment.ai_support_enabled?'enabled':'disabled'}</small></span><Link className="next-step-action" to="/tests">View test</Link></div>)}</div>:<div className="dashboard-empty"><p>No scheduled tests are currently available.</p></div>}</section>
      </div>
      {weak.length > 0 && <section className="recommended-next"><strong>Recommended next step</strong><span>Review {weak[0].topic_title}, then practise again to move toward 70% mastery.</span><Link className="next-step-action" to={`/study/${weak[0].topic_id}?title=${encodeURIComponent(weak[0].topic_title)}`}>Review topic</Link></section>}
    </div>
  )
}
