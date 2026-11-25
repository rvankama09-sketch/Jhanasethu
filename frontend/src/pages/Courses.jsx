import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { api } from '../lib/api'

export default function Courses() {
  const { user } = useAuth()
  const [courses, setCourses] = useState([])
  const [joinCode, setJoinCode] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const loadCourses = async () => setCourses(await api.listCourses())
  useEffect(() => {
    let cancelled = false
    api.listCourses().then((rows) => !cancelled && setCourses(rows)).catch(() => !cancelled && setError('Courses could not be loaded.')).finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [])

  async function join(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const course = await api.joinCourse(joinCode)
      await loadCourses()
      setJoinCode('')
      setNotice(`Joined ${course.title}. Its syllabus topics are now in your learning path.`)
    } catch (requestError) {
      setError(requestError.message || 'The join code could not be used.')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <div className="dashboard-content">Loading courses...</div>
  if (user?.role === 'management') return <div className="dashboard-content"><section className="dashboard-panel dashboard-empty"><p>Course enrollment is not available for management accounts.</p><Link to="/management" className="dashboard-panel-link">Return to overview</Link></section></div>
  if (user?.role === 'instructor') return <div className="dashboard-content"><div className="dashboard-heading"><div><div className="dashboard-eyebrow">Faculty / Classes</div><h1>My classes</h1><p>Create a class from a ready syllabus and share its join code.</p></div><Link to="/faculty/syllabus" className="btn-primary px-4 py-2">Create a class</Link></div><CourseList courses={courses} faculty /></div>

  return (
    <div className="dashboard-content">
      <div className="dashboard-heading"><div><div className="dashboard-eyebrow">Student / Courses</div><h1>My courses</h1><p>Join a faculty class with its course code.</p></div><Link to="/learning-path" className="btn-secondary px-4 py-2">My learning path</Link></div>
      <div className="dashboard-columns">
        <section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Join a class</h2><p>Enter the join code shared by your faculty member.</p></div></div><form className="form-stack p-5" onSubmit={join}><label>Class join code<input required value={joinCode} onChange={(event) => setJoinCode(event.target.value.toUpperCase())} placeholder="A1B2C3D4" maxLength={12} autoCapitalize="characters" /></label>{error && <p className="text-sm text-[var(--color-rust)]" role="alert">{error}</p>}{notice && <p className="text-sm text-[var(--color-forest)]" role="status">{notice}</p>}<button className="btn-primary px-4 py-2" disabled={busy || !joinCode.trim()}>{busy ? 'Joining...' : 'Join course'}</button></form></section>
        <section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Enrolled courses</h2><p>Your approved subject paths.</p></div></div><CourseList courses={courses} /></section>
      </div>
    </div>
  )
}

function CourseList({ courses, faculty = false }) {
  if (!courses.length) return <div className="dashboard-empty"><p>{faculty ? 'No classes yet. Upload a syllabus to create your first class.' : 'You have not joined a class yet.'}</p></div>
  return <div className="course-list">{courses.map((course) => <article className="course-list-row" key={course.id}><div className="course-list-mark">{course.title.slice(0, 1).toUpperCase()}</div><div className="course-list-copy"><strong>{course.title}</strong><small>{course.student_count} enrolled learners · {course.document_name}</small></div>{faculty && course.join_code && <code className="join-code">{course.join_code}</code>}<Link className="dashboard-panel-link" to={faculty ? '/faculty' : `/learning-path?course=${course.id}`}>Open</Link></article>)}</div>
}
