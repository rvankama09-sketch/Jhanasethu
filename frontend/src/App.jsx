import { Route, Routes } from 'react-router-dom'
import Nav from './components/Nav'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Dashboard from './pages/Dashboard'
import Upload from './pages/Upload'
import DiagnosticQuiz from './pages/DiagnosticQuiz'
import Chat from './pages/Chat'
import Quiz from './pages/Quiz'
import StudyKit from './pages/StudyKit'
import Study from './pages/Study'
import Progress from './pages/Progress'
import FacultyDashboard from './pages/FacultyDashboard'
import ManagementDashboard from './pages/ManagementDashboard'
import LearningPath from './pages/LearningPath'
import StudentTests from './pages/StudentTests'
import Assessment from './pages/Assessment'
import Courses from './pages/Courses'
import { useAuth } from './context/AuthContext'

function RoleDashboard() {
  const { user } = useAuth()
  if (user?.role === 'management') return <ManagementDashboard />
  if (user?.role === 'instructor') return <FacultyDashboard />
  return <Dashboard />
}

export default function App() {
  const { user } = useAuth()

  return (
    <div className="app-frame min-h-screen bg-[var(--color-paper)] text-[var(--color-ink)]">
      <Nav />
      <main className={user ? 'app-main' : ''}>
        <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/" element={<ProtectedRoute><RoleDashboard /></ProtectedRoute>} />
        <Route path="/courses" element={<ProtectedRoute><Courses /></ProtectedRoute>} />
        <Route path="/learning-path" element={<ProtectedRoute requireRole="student"><LearningPath /></ProtectedRoute>} />
        <Route path="/tests" element={<ProtectedRoute requireRole="student"><StudentTests /></ProtectedRoute>} />
        <Route path="/assessment/:assessmentId" element={<ProtectedRoute requireRole="student"><Assessment /></ProtectedRoute>} />
        <Route path="/faculty" element={<ProtectedRoute requireRole="instructor"><FacultyDashboard /></ProtectedRoute>} />
        <Route path="/faculty/:section" element={<ProtectedRoute requireRole="instructor"><FacultyDashboard /></ProtectedRoute>} />
        <Route path="/management" element={<ProtectedRoute requireRole="management"><ManagementDashboard /></ProtectedRoute>} />
        <Route path="/management/:section" element={<ProtectedRoute requireRole="management"><ManagementDashboard /></ProtectedRoute>} />
        <Route path="/upload" element={<ProtectedRoute><Upload /></ProtectedRoute>} />

        <Route
          path="/diagnostic"
          element={
            <ProtectedRoute>
              <DiagnosticQuiz />
            </ProtectedRoute>
          }
        />
        
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <Chat />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quiz/:topicId"
          element={
            <ProtectedRoute>
              <Quiz />
            </ProtectedRoute>
          }
        />
        <Route
          path="/study/:topicId"
          element={
            <ProtectedRoute>
              <Study />
            </ProtectedRoute>
        }
        />
        <Route
          path="/study-kit/:topicId"
          element={
            <ProtectedRoute>
              <StudyKit />
            </ProtectedRoute>
          }
        />
        <Route path="/progress" element={<ProtectedRoute requireRole="student"><Progress /></ProtectedRoute>} />
        </Routes>
      </main>
    </div>
  )
}
