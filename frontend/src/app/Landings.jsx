import { Navigate } from 'react-router-dom';
import { landingFor, useAuth } from '../auth/AuthContext.jsx';

export function RoleLandingRedirect() {
  const { user } = useAuth();
  return <Navigate to={landingFor(user.role)} replace />;
}

function Placeholder({ title, description }) {
  return (
    <section className="page">
      <h1>{title}</h1>
      <p>{description}</p>
      <p className="text-muted">Chức năng chi tiết sẽ được triển khai ở lát cắt tiếp theo.</p>
    </section>
  );
}

export function AgentLanding() {
  return <Placeholder title="Vé hỗ trợ" description="Khu vực làm việc của nhân viên: danh sách và xử lý vé hỗ trợ." />;
}

export function AdminLanding() {
  return <Placeholder title="Quản trị hệ thống" description="Khu vực của quản trị viên: người dùng, nhóm và chính sách SLA." />;
}
