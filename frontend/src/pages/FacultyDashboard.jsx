import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api } from '../lib/api'

const viewTitle = {
  '': 'My class learning overview',
  syllabus: 'Syllabus mapping',
  approvals: 'Question approvals',
  assessments: 'Assessments',
  gaps: 'Class gap map',
  'ai-controls': 'AI operating controls',
  reports: 'Class reports',
}

const masteryTone = (score) => score >= 0.8 ? 'mastered' : score >= 0.6 ? 'on-track' : 'at-risk'

function Metric({ label, value, note, tone = 'blue' }) {
  return <div className={`dashboard-metric accent-${tone}`}><span className="dashboard-metric-label">{label}</span><strong className="dashboard-metric-value">{value}</strong><span className="dashboard-metric-note">{note}</span></div>
}

function TopicList({ topics = [] }) {
  if (!topics.length) return <div className="dashboard-empty"><p>No learner mastery data has been recorded for this class yet.</p></div>
  return <div className="topic-list">{topics.map((topic) => <div className="topic-row" key={topic.topic_id}><span className="topic-row-title">{topic.topic_title}</span><span className="topic-row-meta">{topic.student_count} students · {Math.round(topic.average_mastery * 100)}%</span><div className="topic-progress-track"><div className={`topic-progress-fill ${masteryTone(topic.average_mastery)}`} style={{ width: `${Math.round(topic.average_mastery * 100)}%` }} /></div></div>)}</div>
}

function NoCourse({ onUpload }) {
  return <div className="dashboard-panel dashboard-empty"><p>Create a class from a ready syllabus to view class mastery and learner gaps.</p><Link className="btn-primary px-4 py-2 text-sm" to="/faculty/syllabus" onClick={onUpload}>Open syllabus setup</Link></div>
}

export default function FacultyDashboard() {
  const location = useLocation()
  const section = location.pathname.split('/')[2] || ''
  const [courses, setCourses] = useState([])
  const [documents, setDocuments] = useState([])
  const [selectedCourseId, setSelectedCourseId] = useState('')
  const [courseDetail, setCourseDetail] = useState(null)
  const [cohort, setCohort] = useState(null)
  const [heatmap, setHeatmap] = useState(null)
  const [drafts, setDrafts] = useState([])
  const [assessments, setAssessments] = useState([])
  const [selectedDocumentId, setSelectedDocumentId] = useState('')
  const [newCourseTitle, setNewCourseTitle] = useState('')
  const [topicId, setTopicId] = useState('')
  const [questionCount, setQuestionCount] = useState(5)
  const [assessmentTitle, setAssessmentTitle] = useState('Topic assessment')
  const [scheduledAt, setScheduledAt] = useState('')
  const [duration, setDuration] = useState(45)
  const [allowAi, setAllowAi] = useState(false)
  const [approvedDraftId, setApprovedDraftId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const selectedCourse = courses.find((course) => course.id === selectedCourseId) || null
  const readyDocuments = documents.filter((document) => document.document_type === 'syllabus' && document.status === 'ready')
  const topics = courseDetail?.topics || []
  const topicById = useMemo(() => new Map(topics.map((topic) => [topic.id, topic])), [topics])
  const pendingDrafts = drafts.filter((draft) => draft.status === 'pending')
  const topicData = cohort?.topics || []
  const averageMastery = topicData.length ? topicData.reduce((sum, topic) => sum + topic.average_mastery, 0) / topicData.length : 0
  const supportTopics = topicData.filter((topic) => topic.average_mastery < 0.6)
  const learnerTopicRecords = topicData.reduce((sum, topic) => sum + (topic.student_count || 0), 0)

  async function loadCourses() {
    const [courseRows, docRows] = await Promise.all([api.listCourses(), api.listSyllabi()])
    setCourses(courseRows)
    setDocuments(docRows)
    setSelectedCourseId((current) => current || courseRows[0]?.id || '')
    setSelectedDocumentId((current) => current || docRows.find((doc) => doc.status === 'ready' && doc.document_type === 'syllabus')?.id || '')
  }

  useEffect(() => {
    let cancelled = false
    Promise.all([api.listCourses(), api.listSyllabi()])
      .then(([courseRows, docRows]) => {
        if (cancelled) return
        setCourses(courseRows)
        setDocuments(docRows)
        setSelectedCourseId((current) => current || courseRows[0]?.id || '')
        setSelectedDocumentId((current) => current || docRows.find((doc) => doc.status === 'ready' && doc.document_type === 'syllabus')?.id || '')
      })
      .catch(() => !cancelled && setError('Faculty data could not be loaded.'))
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!selectedCourseId) {
      setCourseDetail(null)
      setCohort(null)
      setDrafts([])
      setAssessments([])
      return
    }
    let cancelled = false
    Promise.all([
      api.getCourse(selectedCourseId),
      api.progressCohort(selectedCourseId),
      api.progressCohortHeatmap(selectedCourseId),
      api.facultyQuestionDrafts(selectedCourseId),
      api.facultyAssessments(selectedCourseId),
    ]).then(([detail, cohortData, heatmapData, draftData, assessmentData]) => {
      if (cancelled) return
      setCourseDetail(detail)
      setCohort(cohortData)
      setHeatmap(heatmapData)
      setDrafts(draftData)
      setAssessments(assessmentData)
      setTopicId((current) => current || detail.topics?.[0]?.id || '')
    }).catch(() => !cancelled && setError('This class dashboard could not be loaded.'))
    return () => { cancelled = true }
  }, [selectedCourseId])

  const perform = async (action, successMessage) => {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await action()
      setNotice(successMessage)
    } catch (requestError) {
      setError(requestError.message || 'The requested action could not be completed.')
    } finally {
      setBusy(false)
    }
  }

  const createCourse = (event) => {
    event.preventDefault()
    perform(async () => {
      const course = await api.createCourse({ title: newCourseTitle, document_id: selectedDocumentId })
      await loadCourses()
      setSelectedCourseId(course.id)
      setNewCourseTitle('')
    }, 'Class created. Share its join code from My classes.')
  }

  const generateDraft = (event) => {
    event.preventDefault()
    if (!selectedCourseId || !topicId) return
    perform(async () => {
      const draft = await api.createFacultyQuestionDraft(selectedCourseId, { topic_id: topicId, num_questions: Number(questionCount) })
      setDrafts((current) => [draft, ...current])
    }, 'Question draft created and added to the approval queue.')
  }

  const reviewDraft = (draftId, status) => perform(async () => {
    await api.reviewFacultyQuestionDraft(draftId, status)
    const rows = await api.facultyQuestionDrafts(selectedCourseId)
    setDrafts(rows)
  }, `Question set ${status}.`)

  const createAssessment = (event) => {
    event.preventDefault()
    if (!selectedCourseId || !topicId) return
    perform(async () => {
      const assessment = await api.createFacultyAssessment(selectedCourseId, {
        topic_id: topicId,
        title: assessmentTitle,
        scheduled_at: scheduledAt || null,
        duration_minutes: Number(duration),
        ai_support_enabled: allowAi,
        question_draft_id: approvedDraftId || null,
      })
      setAssessments((current) => [...current, assessment])
      setAssessmentTitle('Topic assessment')
      setScheduledAt('')
    }, scheduledAt ? 'Assessment scheduled for enrolled learners.' : 'Assessment saved as a draft.')
  }

  const heading = viewTitle[section] || viewTitle['']

  return (
    <div className="dashboard-content">
      <div className="dashboard-heading">
        <div><div className="dashboard-eyebrow">Learning intelligence / Faculty</div><h1>{heading}</h1><p>{selectedCourse ? `${selectedCourse.title} · ${selectedCourse.student_count} enrolled learners` : 'Class readiness, question approvals, assessments, and learner support.'}</p></div>
        <label className="filter-control">Class<select value={selectedCourseId} onChange={(event) => { setSelectedCourseId(event.target.value); setTopicId('') }}><option value="">Select class</option>{courses.map((course) => <option value={course.id} key={course.id}>{course.title}</option>)}</select></label>
      </div>
      <div className="dashboard-breadcrumb">Faculty <span>/</span> {selectedCourse?.title || 'Classes'} {section && <><span>/</span> {heading}</>}</div>
      {error && <p className="mb-4 text-sm text-[var(--color-rust)]" role="alert">{error}</p>}
      {notice && <p className="mb-4 text-sm text-[var(--color-forest)]" role="status">{notice}</p>}

      {!courses.length && section !== 'syllabus' ? <NoCourse /> : null}

      {section === '' && selectedCourse && <>
        <section className="dashboard-metrics" aria-label="Class summary">
          <Metric label="Students in class" value={cohort?.student_count ?? selectedCourse.student_count} note="Assigned cohort" />
          <Metric label="Class mastery" value={`${Math.round(averageMastery * 100)}%`} note={`${learnerTopicRecords} learner-topic results`} tone="green" />
          <Metric label="Questions to approve" value={pendingDrafts.length} note="Drafts not yet student-facing" tone="amber" />
          <Metric label="Topics to reteach" value={supportTopics.length} note="Below the 60% faculty gap threshold" tone="red" />
        </section>
        <div className="dashboard-columns">
          <section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Topic mastery</h2><p>Select a topic to inspect readiness and cohort gaps.</p></div><Link to="/faculty/gaps" className="dashboard-panel-link">Open gap map</Link></div><TopicList topics={topicData} /></section>
          <section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Teaching action queue</h2><p>Actions based on current class records.</p></div></div><div className="next-step-list"><div className="next-step"><span className="next-step-number">01</span><span className="next-step-copy"><strong>Review question drafts</strong><small>{pendingDrafts.length} awaiting faculty decision</small></span><Link className="next-step-action" to="/faculty/approvals">Review</Link></div><div className="next-step"><span className="next-step-number">02</span><span className="next-step-copy"><strong>Prepare a topic assessment</strong><small>{assessments.length} draft or scheduled</small></span><Link className="next-step-action" to="/faculty/assessments">Prepare</Link></div><div className="next-step"><span className="next-step-number">03</span><span className="next-step-copy"><strong>Support low-mastery topics</strong><small>{supportTopics.length} below 60%</small></span><Link className="next-step-action" to="/faculty/gaps">Inspect</Link></div></div></section>
        </div>
      </>}

      {section === 'syllabus' && <div className="dashboard-columns">
        <section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Syllabus readiness</h2><p>Only ready syllabi can be attached to a class.</p></div><Link to="/upload" className="dashboard-panel-link">Upload material</Link></div>{documents.length ? <div className="topic-list">{documents.map((doc) => <div className="topic-row" key={doc.id}><span className="topic-row-title">{doc.filename}</span><span className={`status-pill ${doc.status === 'ready' ? 'mastered' : doc.status === 'failed' ? 'at-risk' : 'needs-focus'}`}>{doc.status}</span><small>{doc.document_type.replace('_', ' ')}</small></div>)}</div> : <div className="dashboard-empty"><p>No syllabus uploaded yet.</p><Link to="/upload" className="btn-primary px-4 py-2 text-sm">Upload syllabus</Link></div>}</section>
        <section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Create a class</h2><p>Connect an approved syllabus to a learner cohort.</p></div></div><form className="form-stack p-5" onSubmit={createCourse}><label>Class name<input required value={newCourseTitle} onChange={(event) => setNewCourseTitle(event.target.value)} placeholder="Data Structures · Semester 5" /></label><label>Ready syllabus<select required value={selectedDocumentId} onChange={(event) => setSelectedDocumentId(event.target.value)}><option value="">Choose a syllabus</option>{readyDocuments.map((doc) => <option key={doc.id} value={doc.id}>{doc.filename}</option>)}</select></label><button className="btn-primary px-4 py-2" disabled={busy || !readyDocuments.length}>{busy ? 'Creating...' : 'Create class'}</button></form></section>
      </div>}

      {section === 'approvals' && selectedCourse && <div className="dashboard-stack">
        <section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Generate a question draft</h2><p>AI drafts remain private until a faculty member approves them.</p></div></div><form className="form-inline p-4" onSubmit={generateDraft}><label>Topic<select value={topicId} onChange={(event) => setTopicId(event.target.value)} required><option value="">Select topic</option>{topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.title}</option>)}</select></label><label>Questions<input type="number" min="1" max="20" value={questionCount} onChange={(event) => setQuestionCount(event.target.value)} /></label><button className="btn-primary px-4 py-2" disabled={busy || !topics.length}>{busy ? 'Generating...' : 'Generate draft'}</button></form></section>
        <section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Approval queue</h2><p>Approve or reject each generated question set.</p></div><span className="dashboard-date">{pendingDrafts.length} pending</span></div>{drafts.length ? <div className="draft-list">{drafts.map((draft) => <article className="draft-card" key={draft.id}><div className="draft-heading"><div><strong>{draft.topic_title}</strong><small>Created {new Date(draft.created_at).toLocaleString()}</small></div><span className={`status-pill ${draft.status === 'approved' ? 'mastered' : draft.status === 'rejected' ? 'at-risk' : 'needs-focus'}`}>{draft.status}</span></div><ol>{draft.questions.map((question, index) => <li key={`${draft.id}-${index}`}><strong>{question.question}</strong><span>Correct answer: {question.options[question.correct_index]}</span></li>)}</ol>{draft.status === 'pending' && <div className="action-row"><button className="btn-secondary px-3 py-2" disabled={busy} onClick={() => reviewDraft(draft.id, 'rejected')}>Reject</button><button className="btn-primary px-3 py-2" disabled={busy} onClick={() => reviewDraft(draft.id, 'approved')}>Approve for assessment</button></div>}</article>)}</div> : <div className="dashboard-empty"><p>No question drafts yet. Generate a topic set to start review.</p></div>}</section>
      </div>}

      {section === 'assessments' && selectedCourse && <div className="dashboard-columns">
        <section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Assessment readiness</h2><p>Set topic, duration, schedule, and the AI support boundary.</p></div></div><form className="form-stack p-5" onSubmit={createAssessment}><label>Assessment title<input required value={assessmentTitle} onChange={(event) => setAssessmentTitle(event.target.value)} /></label><label>Topic<select value={topicId} onChange={(event) => setTopicId(event.target.value)} required><option value="">Select topic</option>{topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.title}</option>)}</select></label><label>Approved question set<select value={approvedDraftId} onChange={(event) => setApprovedDraftId(event.target.value)}><option value="">Generate questions at launch</option>{drafts.filter((draft) => draft.status === 'approved' && draft.topic_id === topicId).map((draft) => <option value={draft.id} key={draft.id}>{draft.topic_title} · {draft.questions.length} questions</option>)}</select></label><div className="form-row"><label>Scheduled start<input type="datetime-local" value={scheduledAt} onChange={(event) => setScheduledAt(event.target.value)} /></label><label>Duration (minutes)<input type="number" min="5" max="240" value={duration} onChange={(event) => setDuration(event.target.value)} /></label></div><label className="toggle-row"><input type="checkbox" checked={allowAi} onChange={(event) => setAllowAi(event.target.checked)} /><span><strong>Allow AI assistance during this assessment</strong><small>When off, tutor chat, lesson generation, and practice generation are blocked during the scheduled window.</small></span></label><button className="btn-primary px-4 py-2" disabled={busy || !topics.length}>{busy ? 'Saving...' : scheduledAt ? 'Schedule assessment' : 'Save as draft'}</button></form></section>
        <section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Scheduled assessments</h2><p>Faculty-defined scope and support policy.</p></div></div>{assessments.length ? <div className="next-step-list">{assessments.map((assessment) => <div className="next-step" key={assessment.id}><span className="next-step-number">{assessment.duration_minutes}</span><span className="next-step-copy"><strong>{assessment.title}</strong><small>{assessment.topic_title} · {assessment.scheduled_at ? new Date(assessment.scheduled_at).toLocaleString() : 'Not scheduled'}</small><small>AI assistance {assessment.ai_support_enabled ? 'enabled' : 'disabled'}</small></span><span className={`status-pill ${assessment.status === 'scheduled' ? 'on-track' : 'needs-focus'}`}>{assessment.status}</span></div>)}</div> : <div className="dashboard-empty"><p>No assessments set up yet.</p></div>}</section>
      </div>}

      {section === 'gaps' && selectedCourse && <div className="dashboard-stack"><section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Class gap map</h2><p>Student mastery by topic. Empty cells mean no score is recorded yet.</p></div><div className="legend-inline"><span><i className="status-dot mastered" />80%+</span><span><i className="status-dot needs-focus" />60-79%</span><span><i className="status-dot at-risk" />Below 60%</span></div></div><div className="data-table-wrap"><table className="data-table heatmap-table"><thead><tr><th>Learner</th>{(heatmap?.topics || []).slice(0, 7).map((topic) => <th key={topic.id}>{topic.title}</th>)}</tr></thead><tbody>{(heatmap?.students || []).map((student) => <tr key={student.id}><td>{student.email}</td>{(heatmap?.topics || []).slice(0, 7).map((topic) => {const score=student.mastery[topic.id];return <td key={topic.id}><span className={`heatmap-cell ${score == null ? 'unscored' : score >= 0.8 ? 'high' : score >= 0.6 ? 'medium' : 'low'}`}>{score == null ? '—' : Math.round(score*100)}</span></td>})}</tr>)}</tbody></table>{!heatmap?.students?.length && <div className="dashboard-empty"><p>Enrolled learners appear once they join this class.</p></div>}</div></section><section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Priority teaching focus</h2><p>{supportTopics.length} topic averages below the proposed 60% class threshold.</p></div></div>{supportTopics.length ? <div className="next-step-list">{supportTopics.map((topic, index) => <div className="next-step" key={topic.topic_id}><span className="next-step-number">{index + 1}</span><span className="next-step-copy"><strong>{topic.topic_title}</strong><small>{topic.student_count} learner records · {Math.round(topic.average_mastery * 100)}% class average</small></span><Link className="next-step-action" to="/faculty/assessments">Prepare review</Link></div>)}</div> : <div className="dashboard-empty"><p>No topics are below the class threshold.</p></div>}</section></div>}

      {section === 'ai-controls' && selectedCourse && <div className="dashboard-columns"><section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Faculty-defined AI boundary</h2><p>Settings are attached to each scheduled assessment.</p></div></div><div className="policy-list"><div><span className="policy-icon allowed">+</span><span><strong>Course-scope explanations</strong><small>Answers are grounded in the uploaded material and permitted topics.</small></span></div><div><span className="policy-icon allowed">+</span><span><strong>Practice hints and examples</strong><small>Available during normal study and practice.</small></span></div><div><span className="policy-icon blocked">-</span><span><strong>Scheduled assessments</strong><small>AI chat, lessons, study kits, and practice generation are blocked when an assessment is active and its AI option is off.</small></span></div></div><Link className="btn-primary inline-block px-4 py-2 m-5 text-sm" to="/faculty/assessments">Configure an assessment</Link></section><section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Assessment policies</h2><p>Current AI assistance settings for this class.</p></div></div>{assessments.length ? <div className="next-step-list">{assessments.map((assessment) => <div className="next-step" key={assessment.id}><span className={`status-dot ${assessment.ai_support_enabled ? 'on-track' : 'at-risk'}`} /><span className="next-step-copy"><strong>{assessment.title}</strong><small>{assessment.ai_support_enabled ? 'Assistance permitted' : 'Assistance disabled'}</small></span><span className="topic-row-meta">{assessment.duration_minutes} min</span></div>)}</div> : <div className="dashboard-empty"><p>No assessment policies have been configured.</p></div>}</section></div>}

      {section === 'reports' && selectedCourse && <div className="dashboard-stack"><section className="dashboard-metrics"><Metric label="Class enrollment" value={cohort?.student_count ?? 0} note="Current enrolled learners" /><Metric label="Average mastery" value={`${Math.round(averageMastery * 100)}%`} note="Across recorded topic results" tone="green" /><Metric label="Learning events" value={cohort?.activity_last_7_days ?? 0} note="Last seven days" /><Metric label="Support topics" value={supportTopics.length} note="Under 60% average" tone="red" /></section><section className="dashboard-panel"><div className="dashboard-panel-header"><div><h2>Topic report</h2><p>Course-level mastery and learner record counts.</p></div></div><TopicList topics={topicData} /></section></div>}
    </div>
  )
}
