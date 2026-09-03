import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext.jsx';
import '../styles/auth.css';

// Mirrors backend deps._FEATURE_SCOPES (Task 5).
const NAV = [
  { to: '/app/tickets', label: 'Vé hỗ trợ', roles: ['AGENT', 'MANAGER', 'ADMIN'] },
  { to: '/app/dashboard', label: 'Bảng điều khiển', roles: ['AGENT', 'MANAGER', 'ADMIN'] },
  { to: '/app/admin', label: 'Quản trị', roles: ['ADMIN'] },
];

export default function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const items = NAV.filter((entry) => entry.roles.includes(user.role));

  async function handleLogout() {
    try {
      await logout();
    } finally {
      navigate('/login', { replace: true });
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <strong className="app-brand">Hệ thống hỗ trợ khách hàng</strong>
        <nav className="app-nav" aria-label="Điều hướng chính">
          {items.map((entry) => (
            <NavLink
              key={entry.to}
              to={entry.to}
              className={({ isActive }) => (isActive ? 'app-nav-link active' : 'app-nav-link')}
            >
              {entry.label}
            </NavLink>
          ))}
        </nav>
        <div className="app-user">
          <span>{user.full_name}</span>
          <span className="role-badge">{user.role}</span>
          <button type="button" className="btn-link" onClick={handleLogout}>Đăng xuất</button>
        </div>
      </header>
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  );
}
