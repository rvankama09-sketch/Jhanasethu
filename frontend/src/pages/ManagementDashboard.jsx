import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'

const views = [
  { to: '/management', label: 'Overview', end: true },
  { to: '/management/drilldown', label: 'Course drill-down' },
  { to: '/management/adoption', label: 'Adoption' },
  { to: '/management/interventions', label: 'Interventions' },
  { to: '/management/reports', label: 'Reports' },
]

function Metric({ label, value, note, tone = 'blue' }) {
  return (
    <div className={`dashboard-metric accent-${tone}`}>
      <span className="dashboard-metric-label">{label}</span>
      <strong className="dashboard-metric-value">{value}</strong>
      <span className="dashboard-metric-note">{note}</span>
    </div>
  )
}

function PageHeader({ eyebrow, title, description }) {
  return (
    <div className="dashboard-heading">
      <div>
        <div className="dashboard-eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="dashboard-date">Institution-wide · Last 7 days</div>
    </div>
  )
}

function CourseRows({ courses, selectedCourse, onSelect }) {
  if (!courses.length) {
    return <div className="dashboard-empty"><p>No courses are available for institution drill-down yet.</p></div>
  }
  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead><tr><th>Course</th><th>Faculty owner</th><th>Learners</th><th>Topics</th><th>Mastery</th><th /></tr></thead>
        <tbody>
          {courses.map((course) => (
            <tr key={course.course_id} className={selectedCourse === course.course_id ? 'row-selected' : ''}>
              <td><strong>{course.course_title}</strong></td>
              <td>{course.faculty_email}</td>
              <td>{course.student_count}</td>
              <td>{course.topic_count}</td>
              <td><span className={`status-pill ${course.average_mastery >= 0.8 ? 'mastered' : course.average_mastery >= 0.6 ? 'on-track' : 'at-risk'}`}>{Math.round(course.average_mastery * 100)}%</span></td>
              <td><button className="table-action" onClick={() => onSelect(course.course_id)}>Open topics</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function InterventionList({ items }) {
  if (!items.length) {
    return <div className="dashboard-empty"><p>No topics are currently below the 60% support threshold.</p></div>
  }
  return (
    <div className="next-step-list">
      {items.map((item, index) => (
        <div className="next-step" key={`${item.course_title}-${item.topic_id}`}>
          <span className="next-step-number">{String(index + 1).padStart(2, '0')}</span>
          <span className="next-step-copy">
            <strong>{item.course_title} / {item.topic_title}</strong>
            <small>{item.student_count} learner records · {Math.round(item.average_mastery * 100)}% average mastery</small>
          </span>
          <span className="badge-review px-2 py-1 text-[10px]">At risk</span>
        </div>
      ))}
    </div>
  )
}

function ActivityChart({ daily = [] }) {
  const maximum = Math.max(1, ...daily.map((day) => day.count))
  return (
    <div className="activity-chart" role="img" aria-label="Student learning activity over the last seven days">
      {daily.map((day) => (
        <div className="activity-column" key={day.date}>
          <span className="activity-count">{day.count}</span>
          <div className="activity-track"><span style={{ height: `${Math.max(4, day.count / maximum * 100)}%` }} /></div>
          <small>{new Date(`${day.date}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short' })}</small>
        </div>
      ))}
    </div>
  )
}

export default function ManagementDashboard() {
  const location = useLocation()
  const navigate = useNavigate()
  const section = location.pathname.split('/')[2] || 'overview'
  const [metrics, setMetrics] = useState(null)
  const [adoption, setAdoption] = useState(null)
  const [searchParams, setSearchParams] = useSearchParams()
  const [courses, setCourses] = useState([])
  const [selectedCourse, setSelectedCourse] = useState(searchParams.get('course') || '')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    Promise.all([api.managementMetrics(), api.managementDrilldown(), api.managementAdoption()])
      .then(([metricData, courseData, adoptionData]) => {
        if (cancelled) return
        setMetrics(metricData)
        setCourses(courseData)
        setAdoption(adoptionData)
      })
      .catch(() => !cancelled && setError('Institution analytics could not be loaded.'))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [])

  const selected = courses.find((course) => course.course_id === selectedCourse) || null
  const selectCourse = (courseId) => {
    setSelectedCourse(courseId)
    setSearchParams(courseId ? { course: courseId } : {})
  }
  const interventions = adoption?.interventions ?? []
  const filteredInterventions = selected
    ? interventions.filter((item) => item.course_title === selected?.course_title)
    : interventions
  const supportRecordCount = filteredInterventions.reduce((total, item) => total + item.student_count, 0)
  const sectionMetrics = section === 'drilldown'
    ? [
        { label: 'Students in course', value: selected?.student_count ?? 0, note: 'Enrolled cohort', tone: 'blue' },
        { label: 'Course mastery', value: `${Math.round((selected?.average_mastery ?? 0) * 100)}%`, note: 'Average across recorded results', tone: 'green' },
        { label: 'Assessments completed', value: selected?.assessments_completed ?? 0, note: 'Recorded quiz activity', tone: 'green' },
        { label: 'Topics needing support', value: selected?.topics?.filter((topic) => topic.average_mastery < 0.6).length ?? 0, note: 'Below 60% topic mastery', tone: 'amber' },
      ]
    : section === 'adoption'
      ? [
          { label: 'Weekly active students', value: adoption?.active_students ?? 0, note: 'Unique learners active in 7 days', tone: 'blue' },
          { label: 'Faculty engagement', value: `${adoption?.active_faculty ?? 0} / ${adoption?.faculty_count ?? 0}`, note: 'Faculty with activity this week', tone: 'green' },
          { label: 'Assessments completed', value: adoption?.completed_assessments_last_30_days ?? 0, note: 'Student assessments, last 30 days', tone: 'amber' },
          { label: 'Open support signals', value: interventions.length, note: `${supportRecordCount} learner-topic records below 60%`, tone: 'amber' },
        ]
      : section === 'interventions'
        ? [
            { label: 'Priority topics', value: filteredInterventions.length, note: 'Below the 60% mastery threshold', tone: 'red' },
            { label: 'Learner-topic records', value: supportRecordCount, note: 'Across selected course scope', tone: 'amber' },
            { label: 'Courses affected', value: new Set(filteredInterventions.map((item) => item.course_title)).size, note: 'With an active support signal', tone: 'blue' },
            { label: 'Ready syllabi', value: adoption?.ready_syllabi ?? 0, note: 'Available for course learning', tone: 'green' },
          ]
        : [
            { label: 'Active students', value: metrics?.active_students_last_7_days ?? 0, note: `${metrics?.student_count ?? 0} registered students`, tone: 'blue' },
            { label: 'Average mastery', value: `${Math.round((metrics?.average_mastery ?? 0) * 100)}%`, note: 'Across recorded student results', tone: 'green' },
            { label: 'Topics mapped', value: adoption?.mapped_topics ?? 0, note: `${adoption?.ready_syllabi ?? 0} ready syllabi`, tone: 'blue' },
            { label: 'Students needing support', value: adoption?.students_needing_support ?? 0, note: 'Unique learners below 60% mastery', tone: 'red' },
          ]

  if (loading) return <div className="dashboard-content">Loading institution intelligence...</div>

  return (
    <div className="dashboard-content">
      <PageHeader
        eyebrow="Learning intelligence / Management"
        title={section === 'drilldown' ? 'Course performance drill-down' : section === 'adoption' ? 'Adoption and intervention signals' : section === 'interventions' ? 'Institution intervention queue' : section === 'reports' ? 'Institution reports' : 'Institution overview'}
        description={section === 'drilldown' ? 'Move from course performance to topic mastery and learner support.' : section === 'adoption' ? 'Weekly adoption, syllabus readiness, and learning follow-through.' : section === 'interventions' ? 'Priority topics grouped by course and mastery gap.' : 'Academic performance and platform adoption across the institution.'}
      />

      <nav className="dashboard-subnav" aria-label="Management views">
        {views.map((view) => <NavLink key={view.to} to={`${view.to}${selectedCourse ? `?course=${encodeURIComponent(selectedCourse)}` : ''}`} end={view.end} className={({ isActive }) => `dashboard-tab${isActive ? ' is-active' : ''}`}>{view.label}</NavLink>)}
      </nav>

      {error && <p className="mb-4 text-sm text-[var(--color-rust)]">{error}</p>}

      <section className="dashboard-metrics" aria-label="Institution KPIs">{sectionMetrics.map((item) => <Metric key={item.label} {...item} />)}</section>

      {section === 'overview' && (
        <div className="dashboard-columns">
          <section className="dashboard-panel">
            <div className="dashboard-panel-header"><div><h2>Student learning activity</h2><p>Recorded learning events, last seven days.</p></div><Link to="/management/adoption" className="dashboard-panel-link">Adoption details</Link></div>
            <ActivityChart daily={adoption?.daily_activity} />
          </section>
          <section className="dashboard-panel">
            <div className="dashboard-panel-header"><div><h2>Priority support</h2><p>Course topics below 60% average mastery.</p></div><Link to="/management/interventions" className="dashboard-panel-link">Open queue</Link></div>
            <InterventionList items={interventions.slice(0, 4)} />
          </section>
          <section className="dashboard-panel dashboard-panel-wide">
            <div className="dashboard-panel-header"><div><h2>Course performance</h2><p>Select a course to inspect topics and learner cohorts.</p></div><Link to="/management/drilldown" className="dashboard-panel-link">Drill down</Link></div>
                <CourseRows courses={courses.slice(0, 5)} selectedCourse={selectedCourse} onSelect={(id) => { selectCourse(id); navigate(`/management/drilldown?course=${encodeURIComponent(id)}`) }} />
          </section>
        </div>
      )}

      {section === 'drilldown' && (
        <div className="dashboard-stack">
          <section className="dashboard-panel">
            <div className="dashboard-panel-header"><div><h2>Institution / Course / Topic</h2><p>Department and batch fields are not tracked in the current data model; course is the available drill-down level.</p></div><label className="filter-control">Course<select value={selectedCourse} onChange={(event) => selectCourse(event.target.value)}><option value="">All courses</option>{courses.map((course) => <option value={course.course_id} key={course.course_id}>{course.course_title}</option>)}</select></label></div>
            <CourseRows courses={selected ? [selected] : courses} selectedCourse={selectedCourse} onSelect={selectCourse} />
          </section>
          {selected && <section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>{selected.course_title} topic mastery</h2><p>{selected.student_count} enrolled learners · {selected.topic_count} syllabus topics</p></div><span className="dashboard-date">{Math.round(selected.average_mastery * 100)}% cohort mastery</span></div><div className="topic-list">{selected.topics.map((topic) => <div className="topic-row" key={topic.topic_id}><span className="topic-row-title">{topic.topic_title}</span><span className="topic-row-meta">{topic.student_count} results · {Math.round(topic.average_mastery * 100)}%</span><div className="topic-progress-track"><div className={`topic-progress-fill ${topic.average_mastery >= 0.8 ? 'mastered' : topic.average_mastery >= 0.6 ? 'on-track' : 'at-risk'}`} style={{ width: `${Math.round(topic.average_mastery * 100)}%` }} /></div></div>)}</div></section>}
        </div>
      )}

      {(section === 'adoption' || section === 'reports') && (
        <div className="dashboard-columns">
          <section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Adoption signals</h2><p>Observed platform usage; no assigned denominators are inferred.</p></div></div><ActivityChart daily={adoption?.daily_activity} /><div className="signal-grid"><div><strong>{adoption?.active_faculty ?? 0} / {adoption?.faculty_count ?? 0}</strong><span>Faculty active this week</span></div><div><strong>{adoption?.completed_assessments_last_30_days ?? 0}</strong><span>Student assessments completed in 30 days</span></div><div><strong>{adoption?.course_count ?? 0}</strong><span>Courses available</span></div><div><strong>{adoption?.enrollment_count ?? 0}</strong><span>Course enrollments</span></div></div></section>
          <section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Syllabus readiness funnel</h2><p>Actual syllabus and topic records.</p></div></div><div className="funnel-list"><div><span>Ready syllabi</span><strong>{adoption?.ready_syllabi ?? 0}</strong></div><div><span>Topics mapped</span><strong>{adoption?.mapped_topics ?? 0}</strong></div><div><span>Courses created</span><strong>{adoption?.course_count ?? 0}</strong></div><div><span>Learner enrollments</span><strong>{adoption?.enrollment_count ?? 0}</strong></div></div></section>
          <section className="dashboard-panel dashboard-panel-wide"><div className="dashboard-panel-header"><div><h2>From signal to action</h2><p>Every count reflects a persisted course, mastery, or learning-activity record.</p></div><span className="dashboard-date">Review cadence · weekly</span></div><div className="signal-flow"><div><span>Gaps identified</span><strong>{interventions.length}</strong><small>Course-topic gaps</small></div><i aria-hidden="true">›</i><div><span>Learner records</span><strong>{supportRecordCount}</strong><small>Below 60% mastery</small></div><i aria-hidden="true">›</i><div><span>Recent study actions</span><strong>{adoption?.activity_last_7_days ?? 0}</strong><small>Learning events this week</small></div><i aria-hidden="true">›</i><div><span>Assessments</span><strong>{adoption?.completed_assessments_last_30_days ?? 0}</strong><small>Completed in 30 days</small></div></div></section>
        </div>
      )}

      {section === 'interventions' && <section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Priority intervention queue</h2><p>Topics under 60% average mastery, sorted by lowest score first.</p></div><label className="filter-control">Course<select value={selectedCourse} onChange={(event) => selectCourse(event.target.value)}><option value="">All courses</option>{courses.map((course) => <option value={course.course_id} key={course.course_id}>{course.course_title}</option>)}</select></label></div><InterventionList items={filteredInterventions} /></section>}
    </div>
  )
}
