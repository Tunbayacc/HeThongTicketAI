import { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext.jsx';
import { ROLE_SHORT_LABELS, labelOf } from '../lib/labels.js';
import '../styles/shell.css';

// Mirrors backend deps._FEATURE_SCOPES (Task 5).
const NAV = [
  {
    to: '/app/tickets', label: 'Danh sách vé', roles: ['AGENT', 'MANAGER', 'ADMIN'],
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M15 5v2" /><path d="M15 11v2" /><path d="M15 17v2" />
        <path d="M5 5h14a2 2 0 0 1 2 2v3a2 2 0 0 0 0 4v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-3a2 2 0 0 0 0-4V7a2 2 0 0 1 2-2z" />
      </svg>
    ),
  },
  {
    to: '/app/dashboard', label: 'Bảng điều khiển', roles: ['AGENT', 'MANAGER', 'ADMIN'],
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="4" rx="1" />
        <rect x="14" y="11" width="7" height="10" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
  },
  {
    to: '/app/admin', label: 'Quản trị hệ thống', roles: ['ADMIN'],
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    ),
  },
];

export default function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const items = NAV.filter((entry) => entry.roles.includes(user.role));

  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('sidebar-collapsed') === 'true'; } catch { return false; }
  });

  const [mobileOpen, setMobileOpen] = useState(false);

  const [theme, setTheme] = useState(() => {
    try {
      const saved = localStorage.getItem('app-theme');
      if (saved) return saved;
      return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    } catch {
      return 'light';
    }
  });

  useEffect(() => {
    try { localStorage.setItem('sidebar-collapsed', String(collapsed)); } catch { /* ignore */ }
  }, [collapsed]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try { localStorage.setItem('app-theme', theme); } catch { /* ignore */ }
  }, [theme]);

  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        const backdrops = document.querySelectorAll('.admin-modal-backdrop, .modal-backdrop');
        if (backdrops.length > 0) {
          const topBackdrop = backdrops[backdrops.length - 1];
          const closeBtn = topBackdrop.querySelector('.admin-modal-close, .modal-header .btn-secondary, button[aria-label="Đóng"]');
          if (closeBtn) {
            closeBtn.click();
          } else {
            topBackdrop.click();
          }
          return;
        }
        if (mobileOpen) {
          setMobileOpen(false);
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [mobileOpen]);

  function toggleTheme() {
    setTheme((t) => (t === 'dark' ? 'light' : 'dark'));
  }

  async function handleLogout() {
    try {
      await logout();
    } finally {
      navigate('/login', { replace: true });
    }
  }

  return (
    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''} ${mobileOpen ? 'mobile-open' : ''}`}>
      {/* Mobile Top Header (<= 768px down to 360px) */}
      <header className="mobile-header">
        <button
          type="button"
          className="mobile-menu-btn"
          onClick={() => setMobileOpen(true)}
          aria-label="Mở menu điều hướng"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <div className="mobile-brand">
          <span>Hỗ trợ KH</span>
          <span className="mobile-brand-sub">Trợ lý AI</span>
        </div>
        <button
          type="button"
          className="theme-toggle-btn"
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'}
          title={theme === 'dark' ? 'Giao diện sáng' : 'Giao diện tối'}
        >
          {theme === 'dark' ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="5" /><line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" /><line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" /><line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" /><line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          )}
        </button>
      </header>

      {/* Backdrop overlay for mobile drawer */}
      {mobileOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Main Sidebar (Drawer on mobile) */}
      <aside className={`sidebar ${mobileOpen ? 'is-open' : ''}`} aria-label="Điều hướng chính">
        <div className="sidebar-top">
          {!collapsed && (
            <div className="sidebar-brand">
              <svg className="sidebar-logo" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5Z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
              </svg>
              <div className="sidebar-brand-text">
                <span>Hỗ trợ KH</span>
                <span className="sidebar-brand-sub">Trợ lý AI</span>
              </div>
            </div>
          )}
          <div className="sidebar-top-actions">
            <button
              type="button"
              className="theme-toggle-btn desktop-only"
              onClick={toggleTheme}
              aria-label={theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'}
              title={theme === 'dark' ? 'Giao diện sáng' : 'Giao diện tối'}
            >
              {theme === 'dark' ? (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="5" /><line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" /><line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" /><line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" /><line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                </svg>
              ) : (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
              )}
            </button>
            <button
              type="button"
              className="sidebar-toggle desktop-only"
              onClick={() => setCollapsed((c) => !c)}
              aria-label={collapsed ? 'Mở rộng thanh bên' : 'Thu gọn thanh bên'}
              title={collapsed ? 'Mở rộng' : 'Thu gọn'}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                {collapsed
                  ? <><path d="M13 17l5-5-5-5" /><path d="M6 17l5-5-5-5" /></>
                  : <><path d="M11 17l-5-5 5-5" /><path d="M18 17l-5-5 5-5" /></>
                }
              </svg>
            </button>
            <button
              type="button"
              className="sidebar-close-btn mobile-only"
              onClick={() => setMobileOpen(false)}
              aria-label="Đóng menu"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>

        <nav className="sidebar-nav">
          {items.map((entry) => (
            <NavLink
              key={entry.to}
              to={entry.to}
              className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
              title={collapsed ? entry.label : undefined}
              onClick={() => setMobileOpen(false)}
            >
              <span className="sidebar-icon">{entry.icon}</span>
              {!collapsed && <span className="sidebar-label">{entry.label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-user" title={`${user.full_name} (${labelOf(ROLE_SHORT_LABELS, user.role)})`}>
            <span className="sidebar-avatar">{user.full_name.charAt(0).toUpperCase()}</span>
            {!collapsed && (
              <div className="sidebar-user-info">
                <span className="sidebar-user-name">{user.full_name}</span>
                <span className="sidebar-user-role">{labelOf(ROLE_SHORT_LABELS, user.role)}</span>
              </div>
            )}
          </div>
          <button
            type="button"
            className="sidebar-logout"
            onClick={handleLogout}
            title="Đăng xuất khỏi hệ thống"
            aria-label="Đăng xuất"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            {!collapsed && <span>Đăng xuất</span>}
          </button>
        </div>
      </aside>

      <main className="app-content">
        <Outlet />
      </main>
    </div>
  );
}
