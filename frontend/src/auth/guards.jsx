import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext.jsx';

export function ProtectedRoute({ children }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === 'loading') {
    return (
      <div className="page">
        <p>Đang kiểm tra phiên đăng nhập…</p>
      </div>
    );
  }
  if (status === 'signedOut') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}

export function RequireRoles({ roles, children }) {
  const { user } = useAuth();
  if (!user || !roles.includes(user.role)) {
    return (
      <section className="page">
        <h1>Không có quyền truy cập</h1>
        <p>Bạn không có quyền xem khu vực này (403). Hãy liên hệ quản trị viên nếu bạn cho rằng đây là nhầm lẫn.</p>
      </section>
    );
  }
  return children;
}
