import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api/client.js';
import { fmtDateTime } from '../lib/labels.js';
import '../styles/portal.css';

export default function PortalTrackPage() {
  const [params] = useSearchParams();
  const [form, setForm] = useState({
    ticket_code: params.get('code') || '',
    email: params.get('email') || '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null); // PortalTrackResponse | null

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const body = await api.post('/api/public/track', {
        ticket_code: form.ticket_code.trim().toUpperCase(),
        email: form.email.trim().toLowerCase(),
      });
      setResult(body);
    } catch (err) {
      if (err.error_code === 'TICKET_NOT_FOUND' || err.status === 404) {
        setError('Không tìm thấy vé với mã và email này. Vui lòng kiểm tra lại.');
      } else {
        setError(err.message || 'Không thể tra cứu. Vui lòng thử lại.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="portal-layout">
      {/* --- Top Navigation Header --- */}
      <header className="portal-navbar">
        <div className="portal-navbar-inner">
          <Link to="/" className="portal-brand">
            <div className="portal-brand-logo">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5Z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </div>
            <div className="portal-brand-text">
              <span className="portal-brand-title">Cổng Hỗ Trợ Khách Hàng</span>
              <span className="portal-brand-badge">Hỗ Trợ Trực Tuyến 24/7</span>
            </div>
          </Link>

          <nav className="portal-nav-links">
            <Link to="/" className="portal-nav-item">Gửi yêu cầu</Link>
            <Link to="/track" className="portal-nav-item active">Tra cứu tiến độ</Link>
            <Link to="/login" className="portal-nav-btn">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
                <polyline points="10 17 15 12 10 7" />
                <line x1="15" y1="12" x2="3" y2="12" />
              </svg>
              Dành cho nhân viên
            </Link>
          </nav>
        </div>
      </header>

      {/* --- Main Content --- */}
      <main className="portal-container" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 'var(--space-8) var(--space-4)' }}>
        <section className="portal-card" style={{ maxWidth: '640px', margin: '0 auto' }}>
          <div className="portal-form-header" style={{ border: 'none', padding: 0 }}>
            <h1>Tra cứu tiến độ yêu cầu hỗ trợ</h1>
            <p className="text-muted">Nhập mã vé và địa chỉ email đã dùng khi gửi yêu cầu để kiểm tra phản hồi mới nhất.</p>
          </div>

          <form onSubmit={handleSubmit} noValidate className="portal-form">
            <label className="field">
              <span>Mã vé hỗ trợ *</span>
              <input
                value={form.ticket_code}
                onChange={(e) => setForm((f) => ({ ...f, ticket_code: e.target.value }))}
                required
                placeholder="VD: TK-XXXXXXXX"
              />
            </label>

            <label className="field">
              <span>Email người yêu cầu *</span>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                required
                placeholder="ban@example.com"
                autoComplete="email"
              />
            </label>

            {error && <p className="form-error" role="alert">⚠ {error}</p>}

            <button type="submit" className="btn-primary" disabled={submitting} style={{ width: '100%', padding: '12px' }}>
              {submitting ? 'Đang tra cứu…' : 'Tra cứu tiến độ vé'}
            </button>
          </form>

          {result && (
            <div className="track-result" data-testid="track-result">
              <h2>{result.subject}</h2>
              <dl className="track-meta">
                <div><dt>Mã vé</dt><dd>{result.ticket_code}</dd></div>
                <div><dt>Trạng thái</dt><dd><span className="badge badge--open">{labelOfStatus(result.status)}</span></dd></div>
                <div><dt>Ngày gửi</dt><dd>{fmtDateTime(result.created_at)}</dd></div>
                {result.updated_at && <div><dt>Cập nhật lần cuối</dt><dd>{fmtDateTime(result.updated_at)}</dd></div>}
              </dl>

              <h3 style={{ margin: 'var(--space-4) 0 var(--space-2)', fontSize: 'var(--font-size-sm)' }}>Phản hồi từ nhân viên hỗ trợ:</h3>
              {result.comments && result.comments.length > 0 ? (
                <ul className="comment-list">
                  {result.comments.map((c) => (
                    <li key={c.id} className="comment-item">
                      <p className="comment-content">{c.content}</p>
                      <p className="text-muted text-xs" style={{ margin: 0 }}>{fmtDateTime(c.created_at)}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted text-xs">Yêu cầu đang được phân công xử lý, chưa có phản hồi mới.</p>
              )}
            </div>
          )}

          <p className="portal-foot">
            <Link to="/">← Gửi yêu cầu mới</Link> · <Link to="/login">Nhân viên hỗ trợ? Đăng nhập</Link>
          </p>
        </section>
      </main>

      {/* --- Footer --- */}
      <footer className="portal-footer">
        <p style={{ margin: 0 }}>
          © {new Date().getFullYear()} Cổng Hỗ Trợ Khách Hàng AI. Phục vụ 24/7 · Cam kết hỗ trợ nhanh chóng và tận tâm.
        </p>
      </footer>
    </div>
  );
}

function labelOfStatus(s) {
  return ({ OPEN: 'Mở', IN_PROGRESS: 'Đang xử lý', PENDING: 'Chờ bổ sung thông tin', RESOLVED: 'Đã giải quyết', CLOSED: 'Đã đóng' })[s] || s;
}
