import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ProtectedRoute, RequireRoles } from './auth/guards.jsx';
import { AdminLanding, AgentLanding, ManagerLanding, RoleLandingRedirect } from './app/Landings.jsx';
import AppShell from './app/AppShell.jsx';
import HealthPage from './pages/HealthPage.jsx';
import LoginPage from './pages/LoginPage.jsx';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HealthPage />} />
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
                <AgentLanding />
              </RequireRoles>
            }
          />
          <Route
            path="dashboard"
            element={
              <RequireRoles roles={['MANAGER', 'ADMIN']}>
                <ManagerLanding />
              </RequireRoles>
            }
          />
          <Route
            path="admin"
            element={
              <RequireRoles roles={['ADMIN']}>
                <AdminLanding />
              </RequireRoles>
            }
          />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
