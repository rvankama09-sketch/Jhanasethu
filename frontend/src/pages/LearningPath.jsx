import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'

function scoreForTopic(trends, topicId) {
  return trends.find((trend) => trend.topic_id === topicId)?.score ?? 0
}

function toneFor(score) {
  return score >= 0.8 ? 'mastered' : score >= 0.6 ? 'on-track' : score >= 0.4 ? 'needs-focus' : 'at-risk'
}

export default function LearningPath() {
  const [params, setParams] = useSearchParams()
  const [topics, setTopics] = useState([])
  const [plan, setPlan] = useState([])
  const [trends, setTrends] = useState([])
  const [courses, setCourses] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    Promise.all([api.listTopics(), api.getStudyPlan(), api.progressTrends(), api.listCourses()])
      .then(async ([topicRows, planRows, trendData, courseRows]) => {
        if (cancelled) return
        const detailedCourses = await Promise.all(courseRows.map((course) => api.getCourse(course.id).catch(() => course)))
        if (cancelled) return
        setTopics(topicRows)
        setPlan(planRows)
        setTrends(trendData.trends || [])
        setCourses(detailedCourses)
      })
      .catch(() => !cancelled && setError('Your learning path could not be loaded.'))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [])

  const selectedCourse = params.get('course') || ''
  const visibleTopics = useMemo(() => {
    if (!selectedCourse) return topics
    const course = courses.find((item) => item.id === selectedCourse)
    if (!course) return topics
    const courseTopicIds = new Set((course.topics || []).map((topic) => topic.id))
    return topics.filter((topic) => courseTopicIds.has(topic.id))
  }, [topics, courses, selectedCourse])
  const planByTopic = new Map(plan.map((item) => [item.topic_id, item]))
  const rootTopics = visibleTopics.filter((topic) => !topic.parent_id)
  const childrenByParent = new Map()
  visibleTopics.filter((topic) => topic.parent_id).forEach((topic) => {
    const children = childrenByParent.get(topic.parent_id) || []
    children.push(topic)
    childrenByParent.set(topic.parent_id, children)
  })

  if (loading) return <div className="dashboard-content">Loading your learning path...</div>

  return (
    <div className="dashboard-content">
      <div className="dashboard-heading"><div><div className="dashboard-eyebrow">Student / My learning path</div><h1>My learning path</h1><p>Subject to topic to subtopic to learn, practise, and test.</p></div><label className="filter-control">Subject<select value={selectedCourse} onChange={(event) => setParams(event.target.value ? { course: event.target.value } : {})}><option value="">All subjects</option>{courses.map((course) => <option value={course.id} key={course.id}>{course.title}</option>)}</select></label></div>
      <div className="dashboard-breadcrumb">My dashboard <span>/</span> {courses.find((course) => course.id === selectedCourse)?.title || 'All subjects'} <span>/</span> Topic path</div>
      {error && <p className="mb-4 text-sm text-[var(--color-rust)]" role="alert">{error}</p>}

      {!visibleTopics.length ? <section className="dashboard-panel dashboard-empty"><p>No topics are available yet. Join a class or upload a syllabus.</p><Link to="/courses" className="btn-primary px-4 py-2">Browse courses</Link></section> : <div className="path-tree">{rootTopics.map((topic, topicIndex) => {
        const score = scoreForTopic(trends, topic.id)
        const planItem = planByTopic.get(topic.id)
        const children = childrenByParent.get(topic.id) || []
        const title = topic.title
        return <section className="path-subject" key={topic.id}><div className="path-subject-header"><span className="path-step-index">{String(topicIndex + 1).padStart(2, '0')}</span><div className="path-topic-heading"><strong>{title}</strong><small>{topic.difficulty} · {planItem?.status?.replaceAll('_', ' ') || 'Not started'}</small></div><span className={`status-pill ${toneFor(score)}`}>{score ? `${Math.round(score * 100)}% mastery` : 'Not started'}</span></div><div className="path-topic-progress"><div className={`topic-progress-fill ${toneFor(score)}`} style={{ width: `${Math.round(score * 100)}%` }} /></div><div className="path-actions"><Link to={`/study/${topic.id}?title=${encodeURIComponent(title)}`}>Learn</Link><Link to={`/quiz/${topic.id}?title=${encodeURIComponent(title)}`}>Practice</Link><Link to={`/quiz/${topic.id}?title=${encodeURIComponent(title)}`}>Test</Link></div>{children.length > 0 && <div className="path-children">{children.map((child) => { const childScore = scoreForTopic(trends, child.id); return <div className="path-child" key={child.id}><span className={`status-dot ${toneFor(childScore)}`} /><span className="path-child-title">{child.title}</span><span className="path-child-score">{childScore ? `${Math.round(childScore * 100)}%` : 'Not started'}</span><div className="path-child-actions"><Link to={`/study/${child.id}?title=${encodeURIComponent(child.title)}`}>Learn</Link><Link to={`/quiz/${child.id}?title=${encodeURIComponent(child.title)}`}>Practice</Link></div></div> })}</div>}</section>
      })}</div>}

      <section className="dashboard-panel readiness-panel"><div className="dashboard-panel-header"><div><h2>Personal progress signals</h2><p>The student topic target is 70%. Use the mastery bars to see where to review.</p></div></div><div className="status-guide-grid"><div className="status-guide-item"><span className="status-dot mastered" /><span className="status-guide-copy"><strong>Mastered</strong><small>80%+ · At or above target</small></span></div><div className="status-guide-item"><span className="status-dot on-track" /><span className="status-guide-copy"><strong>On track</strong><small>60-79% · Progressing</small></span></div><div className="status-guide-item"><span className="status-dot needs-focus" /><span className="status-guide-copy"><strong>Needs focus</strong><small>40-59% · Below target</small></span></div><div className="status-guide-item"><span className="status-dot at-risk" /><span className="status-guide-copy"><strong>At risk</strong><small>Below 40% · Priority review</small></span></div></div></section>
    </div>
  )
}
