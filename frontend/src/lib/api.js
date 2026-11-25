const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

class ApiError extends Error {
  constructor(message, status, detail) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

function getToken() {
  return localStorage.getItem('jnana_sethu_token')
}

export function setToken(token) {
  if (token) localStorage.setItem('jnana_sethu_token', token)
  else localStorage.removeItem('jnana_sethu_token')
}

async function request(path, { method = 'GET', body, isForm = false, auth = true } = {}) {
  const headers = {}
  if (!isForm) headers['Content-Type'] = 'application/json'
  if (auth) {
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
  })

  let data = null
  const text = await res.text()
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }

  if (!res.ok) {
    const detail = data && data.detail ? data.detail : `Request failed (${res.status})`
    throw new ApiError(typeof detail === 'string' ? detail : JSON.stringify(detail), res.status, detail)
  }
  return data
}

export const api = {
  base: API_BASE,
  signup: (payload) => request('/auth/signup', { method: 'POST', body: payload, auth: false }),
  login: (payload) => request('/auth/login', { method: 'POST', body: payload, auth: false }),
  me: () => request('/auth/me'),

  uploadSyllabus: (file, documentType = 'syllabus') => {
    const form = new FormData()
    form.append('file', file)
    form.append('document_type', documentType)
    return request('/syllabus/upload', { method: 'POST', body: form, isForm: true })
  },
  syllabusStatus: (documentId) => request(`/syllabus/${documentId}/status`),
  listSyllabi: () => request('/syllabus/'),
  deleteSyllabus: (documentId) => request(`/syllabus/${documentId}`, { method: 'DELETE' }),

  generateStudyPlan: () =>
    request('/study-plan/generate', { method: 'POST', body: {} }),
  getStudyPlan: () => request('/study-plan/'),

  listTopics: (documentId) =>
    request(`/topics/${documentId ? `?document_id=${documentId}` : ''}`),

  generateQuiz: (topicId) =>
    request('/quiz/generate', { method: 'POST', body: { topic_id: topicId } }),
  submitQuiz: (quizId, answers) =>
    request('/quiz/submit', { method: 'POST', body: { quiz_id: quizId, answers } }),
  generateDiagnosticQuiz: (numQuestions = 10) =>
    request('/quiz/diagnostic/generate', {
      method: 'POST',
      body: { num_questions: numQuestions },
    }),

  submitDiagnosticQuiz: (quizId, answers) =>
    request('/quiz/diagnostic/submit', {
      method: 'POST',
      body: { quiz_id: quizId, answers },
    }),
  explainAnswer: (quizId, questionIndex) =>
    request(`/quiz/${quizId}/explain-answer/${questionIndex}`),

  generateStudy: (topicId) =>
    request('/study/generate', { method: 'POST', body: { topic_id: topicId } }),

  generateStudyKit: (topicId) =>
    request('/study-kit/generate-advanced', { method: 'POST', body: { topic_id: topicId } }),

  requestRemediation: (topicId, subConcept) =>
    request('/remediation/micro-module', { method: 'POST', body: { topic_id: topicId, sub_concept: subConcept } }),

  sendChatMessage: (message) => request('/chat/message', { method: 'POST', body: { message } }),
  chatHistory: () => request('/chat/history'),

  progressTrends: () => request('/progress/trends'),
  progressActivity: () => request('/progress/activity'),
  progressCohort: (courseId) =>
    request(`/progress/cohort?course_id=${encodeURIComponent(courseId)}`),
  progressCohortHeatmap: (courseId) =>
    request(`/progress/cohort/heatmap?course_id=${encodeURIComponent(courseId)}`),

  listCourses: () => request('/courses/'),
  getCourse: (courseId) => request(`/courses/${courseId}`),
  createCourse: (payload) => request('/courses/', { method: 'POST', body: payload }),
  joinCourse: (joinCode) => request('/courses/join', { method: 'POST', body: { join_code: joinCode } }),

  managementMetrics: () => request('/management/metrics'),
  managementDrilldown: () => request('/management/drilldown'),
  managementAdoption: () => request('/management/adoption'),

  facultyQuestionDrafts: (courseId, status) =>
    request(`/faculty/courses/${courseId}/question-drafts${status ? `?status=${encodeURIComponent(status)}` : ''}`),
  createFacultyQuestionDraft: (courseId, payload) =>
    request(`/faculty/courses/${courseId}/question-drafts`, { method: 'POST', body: payload }),
  reviewFacultyQuestionDraft: (draftId, status) =>
    request(`/faculty/question-drafts/${draftId}`, { method: 'PATCH', body: { status } }),
  facultyAssessments: (courseId) => request(`/faculty/courses/${courseId}/assessments`),
  createFacultyAssessment: (courseId, payload) =>
    request(`/faculty/courses/${courseId}/assessments`, { method: 'POST', body: payload }),
  myAssessments: () => request('/assessments/mine'),
  startAssessment: (assessmentId) =>
    request(`/assessments/${assessmentId}/start`, { method: 'POST', body: {} }),
}

export { ApiError, getToken }

