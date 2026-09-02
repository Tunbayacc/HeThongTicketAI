import { useEffect, useState } from 'react';

export default function HealthPage() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch('/api/health/live').then((r) => r.json()),
      fetch('/api/health/ready').then((r) => (r.ok ? r.json() : r.json().then((b) => ({ ...b, http: r.status })))),
      fetch('/api/health/ai').then((r) => (r.ok ? r.json() : r.json().then((b) => ({ ...b, http: r.status })))),
    ])
      .then(([live, ready, ai]) => setHealth({ live, ready, ai }))
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="page"><p className="error">Không kết nối được backend: {error}</p></div>;
  if (!health) return <div className="page"><p>Đang kiểm tra trạng thái hệ thống…</p></div>;

  return (
    <div className="page">
      <h1>Hệ thống hỗ trợ khách hàng</h1>
      <p>Trạng thái hạ tầng (S0):</p>
      <ul className="status-list">
        <li>Liveness: <strong>{health.live?.status}</strong></li>
        <li>Readiness: <strong>{health.ready?.status}</strong>{health.ready?.message ? ` — ${health.ready.message}` : ''}</li>
        <li>AI provider: <strong>{health.ai?.provider}</strong> ({health.ai?.status})</li>
      </ul>
      <p><a href="/login">Đăng nhập</a></p>
    </div>
  );
}
