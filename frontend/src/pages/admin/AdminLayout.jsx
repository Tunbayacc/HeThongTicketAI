import { NavLink, Outlet, Navigate, useLocation } from 'react-router-dom';
import '../../styles/admin.css';

const TABS = [
  { to: '/app/admin/users', label: 'Người dùng' },
  { to: '/app/admin/teams', label: 'Nhóm hỗ trợ' },
  { to: '/app/admin/sla-policies', label: 'Chính sách SLA' },
  { to: '/app/admin/audit-logs', label: 'Nhật ký hệ thống' },
];

export default function AdminLayout() {
  const location = useLocation();
  if (location.pathname === '/app/admin' || location.pathname === '/app/admin/') {
    return <Navigate to="/app/admin/users" replace />;
  }

  return (
    <div className="admin-layout">
      <div className="admin-header">
        <div>
          <h1 className="admin-title">Quản trị hệ thống</h1>
          <p className="admin-subtitle">Cấu hình người dùng, đội ngũ, SLA và theo dõi nhật ký kiểm toán</p>
        </div>
      </div>
      <nav className="admin-tabs" aria-label="Điều hướng quản trị">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) => (isActive ? 'admin-tab active' : 'admin-tab')}
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <div className="admin-content">
        <Outlet />
      </div>
    </div>
  );
}
