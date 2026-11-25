import { NavLink } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const NAVIGATION = {
  student: {
    home: '/',
    role: 'Student workspace',
    links: [
      { to: '/', label: 'My dashboard', end: true },
      { to: '/learning-path', label: 'My learning path' },
      { to: '/diagnostic', label: 'Practice' },
      { to: '/tests', label: 'Tests' },
      { to: '/progress', label: 'Progress' },
      { to: '/chat', label: 'Learning support' },
    ],
  },
  instructor: {
    home: '/faculty',
    role: 'Faculty workspace',
    links: [
      { to: '/faculty', label: 'My classes', end: true },
      { to: '/faculty/syllabus', label: 'Syllabus' },
      { to: '/faculty/approvals', label: 'Question approvals' },
      { to: '/faculty/assessments', label: 'Assessments' },
      { to: '/faculty/gaps', label: 'Class gaps' },
      { to: '/faculty/ai-controls', label: 'AI controls' },
      { to: '/faculty/reports', label: 'Reports' },
    ],
  },
  management: {
    home: '/management',
    role: 'Management workspace',
    links: [
      { to: '/management', label: 'Institution overview', end: true },
      { to: '/management/drilldown', label: 'Learning outcomes' },
      { to: '/management/adoption', label: 'Adoption' },
      { to: '/management/interventions', label: 'Interventions' },
      { to: '/management/reports', label: 'Reports' },
    ],
  },
}

export default function Nav() {
  const { user, logout } = useAuth()
  const navigation = user ? NAVIGATION[user.role] : null

  if (!user) {
    return (
      <header className="public-header">
        <NavLink to="/" className="brand-lockup">
          <svg width="28" height="28" viewBox="0 0 64 64" aria-hidden="true">
            <circle cx="32" cy="32" r="30" fill="#2B3A67" />
            <circle cx="32" cy="20" r="5" fill="#F6EFDC" />
            <circle cx="20" cy="40" r="5" fill="#F6EFDC" />
            <circle cx="44" cy="40" r="5" fill="#F6EFDC" />
            <path d="M32 20 L20 40 L44 40 Z" stroke="#B8912B" strokeWidth="2" fill="none" />
          </svg>
          <span>Jnana Sethu</span>
        </NavLink>
        <div className="public-actions">
          <NavLink to="/login" className="btn-secondary text-sm px-3 py-1.5">Sign in</NavLink>
          <NavLink to="/signup" className="btn-primary text-sm px-3 py-1.5">Get started</NavLink>
        </div>
      </header>
    )
  }

  return (
    <aside className="app-sidebar">
      <NavLink to={navigation.home} className="sidebar-brand">
        <span className="sidebar-mark" aria-hidden="true">J</span>
        <span className="sidebar-brand-copy">
          <strong>Jnana Sethu</strong>
          <small>Learning intelligence</small>
        </span>
      </NavLink>

      <div className="sidebar-section-label">{navigation.role.replace(' workspace', '')}</div>
      <nav className="sidebar-nav" aria-label="Main navigation">
        {navigation.links.map(({ to, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => `sidebar-link${isActive ? ' is-active' : ''}`}
          >
            <span className="sidebar-link-marker" aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-role">
        <span className="sidebar-role-dot" />
        <span>{navigation.role}</span>
      </div>

      <div className="sidebar-account">
        <span className="account-avatar" aria-hidden="true">
          {(user.full_name || user.email || 'U').slice(0, 1).toUpperCase()}
        </span>
        <span className="account-copy">
          <strong>{user.full_name || user.email?.split('@')[0]}</strong>
          <small>{user.email}</small>
        </span>
        <button onClick={logout} className="sidebar-signout" title="Sign out">
          Sign out
        </button>
      </div>
    </aside>
  )
}
