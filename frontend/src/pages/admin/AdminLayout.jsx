import { NavLink, Outlet, Navigate, useLocation } from 'react-router-dom';
import '../../styles/admin.css';

const TABS = [
  {
    to: '/app/admin/users',
    label: 'Người dùng',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
  },
  {
    to: '/app/admin/teams',
    label: 'Nhóm hỗ trợ',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
        <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
      </svg>
    ),
  },
  {
    to: '/app/admin/sla-policies',
    label: 'Chính sách SLA',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
    ),
  },
  {
    to: '/app/admin/audit-logs',
    label: 'Nhật ký hệ thống',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
    ),
  },
];

export default function AdminLayout() {
  const location = useLocation();
  if (location.pathname === '/app/admin' || location.pathname === '/app/admin/') {
    return <Navigate to="/app/admin/users" replace />;
  }

  return (
    <section className="page admin-page">
      <div className="admin-layout">
        <div className="admin-header">
          <div>
            <div className="admin-title-row">
              <h1 className="admin-title">Quản trị hệ thống</h1>
              <span className="admin-badge-badge">Admin Workspace</span>
            </div>
            <p className="admin-subtitle">Cấu hình tài khoản, phân bổ đội ngũ hỗ trợ, cam kết dịch vụ SLA và giám sát nhật ký kiểm toán</p>
          </div>
        </div>
        <nav className="admin-tabs" aria-label="Điều hướng quản trị">
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) => (isActive ? 'admin-tab active' : 'admin-tab')}
            >
              <span className="admin-tab-icon">{tab.icon}</span>
              <span>{tab.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="admin-content">
          <Outlet />
        </div>
      </div>
    </section>
  );
}
