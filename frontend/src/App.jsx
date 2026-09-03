import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ProtectedRoute, RequireRoles } from './auth/guards.jsx';
import { RoleLandingRedirect } from './app/Landings.jsx';
import AppShell from './app/AppShell.jsx';
import PortalCreatePage from './pages/PortalCreatePage.jsx';
import PortalTrackPage from './pages/PortalTrackPage.jsx';
import HealthPage from './pages/HealthPage.jsx';
import LoginPage from './pages/LoginPage.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import TicketsListPage from './pages/TicketsListPage.jsx';
import TicketDetailPage from './pages/TicketDetailPage.jsx';
import AdminLayout from './pages/admin/AdminLayout.jsx';
import AdminUsersPage from './pages/admin/AdminUsersPage.jsx';
import AdminTeamsPage from './pages/admin/AdminTeamsPage.jsx';
import AdminSlaPage from './pages/admin/AdminSlaPage.jsx';
import AdminAuditPage from './pages/admin/AdminAuditPage.jsx';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<PortalCreatePage />} />
        <Route path="/track" element={<PortalTrackPage />} />
        <Route path="/health" element={<HealthPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/app"
          element={
            <ProtectedRoute>
              <AppShell />
            </ProtectedRoute>
          }
        >
          <Route index element={<RoleLandingRedirect />} />
          <Route
            path="tickets"
            element={
              <RequireRoles roles={['AGENT', 'MANAGER', 'ADMIN']}>
                <TicketsListPage />
              </RequireRoles>
            }
          />
          <Route
            path="tickets/:id"
            element={
              <RequireRoles roles={['AGENT', 'MANAGER', 'ADMIN']}>
                <TicketDetailPage />
              </RequireRoles>
            }
          />
          <Route
            path="dashboard"
            element={
              <RequireRoles roles={['AGENT', 'MANAGER', 'ADMIN']}>
                <DashboardPage />
              </RequireRoles>
            }
          />
          <Route
            path="admin"
            element={
              <RequireRoles roles={['ADMIN']}>
                <AdminLayout />
              </RequireRoles>
            }
          >
            <Route index element={<Navigate to="users" replace />} />
            <Route path="users" element={<AdminUsersPage />} />
            <Route path="teams" element={<AdminTeamsPage />} />
            <Route path="sla-policies" element={<AdminSlaPage />} />
            <Route path="audit-logs" element={<AdminAuditPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
