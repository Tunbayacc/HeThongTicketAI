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
    <div className="portal-page">
      <section className="portal-card">
        <h1>Tra cứu yêu cầu hỗ trợ</h1>
        <p className="text-muted">Nhập mã vé và email bạn đã dùng khi gửi yêu cầu.</p>

        <form onSubmit={handleSubmit} noValidate>
          <label className="field">
            <span>Mã vé *</span>
            <input value={form.ticket_code} onChange={(e) => setForm((f) => ({ ...f, ticket_code: e.target.value }))}
              required placeholder="TK-XXXXXXXX" />
          </label>
          <label className="field">
            <span>Email *</span>
            <input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              required placeholder="ban@example.com" autoComplete="email" />
          </label>

          {error && <p className="form-error" role="alert">{error}</p>}

          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? 'Đang tra cứu…' : 'Tra cứu'}
          </button>
        </form>

        {result && (
          <div className="track-result" data-testid="track-result">
            <h2>{result.subject}</h2>
            <dl className="track-meta">
              <div><dt>Mã vé</dt><dd>{result.ticket_code}</dd></div>
              <div><dt>Trạng thái</dt><dd>{labelOfStatus(result.status)}</dd></div>
              <div><dt>Ngày gửi</dt><dd>{fmtDateTime(result.created_at)}</dd></div>
              {result.updated_at && <div><dt>Cập nhật lần cuối</dt><dd>{fmtDateTime(result.updated_at)}</dd></div>}
            </dl>
            {result.comments && result.comments.length > 0 ? (
              <ul className="comment-list">
                {result.comments.map((c) => (
                  <li key={c.id} className="comment-item">
                    <p className="comment-content">{c.content}</p>
                    <p className="text-muted">{fmtDateTime(c.created_at)}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted">Chưa có phản hồi công khai nào.</p>
            )}
          </div>
        )}

        <p className="portal-foot">
          <Link to="/">← Gửi yêu cầu mới</Link> · <Link to="/login">Nhân viên? Đăng nhập</Link>
        </p>
      </section>
    </div>
  );
}

function labelOfStatus(s) {
  return ({ OPEN: 'Mở', IN_PROGRESS: 'Đang xử lý', PENDING: 'Chờ bổ sung thông tin', RESOLVED: 'Đã giải quyết', CLOSED: 'Đã đóng' })[s] || s;
}
