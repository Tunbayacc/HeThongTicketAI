import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client.js';
import { CATEGORY_LABELS } from '../lib/labels.js';
import '../styles/portal.css';

// SRS 10.1 field rules (mirrored here for inline UX; backend is authoritative).
const MAX_FILES = 5;

function fieldErrors(err) {
  // Uniform envelope: details is a pydantic error list [{loc,msg},...].
  if (!err.details) return err.message;
  const parts = err.details.map((d) => {
    const field = (d.loc || []).filter((s) => typeof s === 'string').join('.');
    return field ? `${field}: ${d.msg}` : d.msg;
  });
  return parts.slice(0, 3).join('; ') || err.message;
}

export default function PortalCreatePage() {
  const [form, setForm] = useState({
    requester_name: '',
    requester_email: '',
    subject: '',
    description: '',
    category: '',
  });
  const [files, setFiles] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);
  const [created, setCreated] = useState(null); // PortalTicketOut | null

  function set(key) {
    return (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) return; // disable double-submit (SRS 7.1.1)
    if (files.length > MAX_FILES) {
      setFormError(`Mỗi yêu cầu tối đa ${MAX_FILES} tệp đính kèm.`);
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      const fd = new FormData();
      fd.append('requester_name', form.requester_name.trim());
      fd.append('requester_email', form.requester_email.trim().toLowerCase());
      fd.append('subject', form.subject.trim());
      fd.append('description', form.description.trim());
      if (form.category) fd.append('category', form.category);
      files.forEach((f) => fd.append('files', f));
      const body = await api.postForm('/api/public/tickets', fd); // 201 PortalTicketOut
      setCreated(body);
    } catch (err) {
      setFormError(err.error_code === 'RATE_LIMITED'
        ? 'Bạn đã gửi quá nhiều yêu cầu trong thời gian ngắn. Vui lòng thử lại sau.'
        : fieldErrors(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (created) {
    return (
      <div className="portal-page">
        <section className="portal-card portal-success" role="status">
          <h1>Đã tiếp nhận yêu cầu hỗ trợ</h1>
          <p>
            Cảm ơn {created.requester_name || 'bạn'}, yêu cầu đã được ghi nhận.
            Vui lòng lưu lại mã vé để tra cứu tiến độ:
          </p>
          <p className="portal-code" data-testid="created-code">{created.ticket_code}</p>
          <p className="text-muted">Trạng thái hiện tại: {labelOfStatus(created.status)}</p>
          <div className="portal-actions">
            <Link className="btn-primary" to={`/track?code=${encodeURIComponent(created.ticket_code)}`}>
              Tra cứu trạng thái
            </Link>
            <Link className="btn-ghost" to="/">Gửi yêu cầu khác</Link>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="portal-page">
      <section className="portal-card">
        <h1>Gửi yêu cầu hỗ trợ</h1>
        <p className="text-muted">Chúng tôi sẽ phản hồi qua email bạn cung cấp. Vui lòng điền đầy đủ thông tin.</p>

        <form onSubmit={handleSubmit} noValidate>
          <label className="field">
            <span>Họ và tên *</span>
            <input value={form.requester_name} onChange={set('requester_name')}
              required minLength={2} maxLength={100} placeholder="Nguyễn Văn A" />
          </label>

          <label className="field">
            <span>Email *</span>
            <input type="email" value={form.requester_email} onChange={set('requester_email')}
              required maxLength={255} placeholder="ban@example.com" autoComplete="email" />
          </label>

          <label className="field">
            <span>Tiêu đề *</span>
            <input value={form.subject} onChange={set('subject')}
              required minLength={5} maxLength={200} placeholder="Mô tả ngắn vấn đề" />
          </label>

          <label className="field">
            <span>Mô tả chi tiết *</span>
            <textarea rows={6} value={form.description} onChange={set('description')}
              required minLength={10} maxLength={20000} placeholder="Mô tả vấn đề bạn gặp phải, các bước đã thực hiện…" />
          </label>

          <label className="field">
            <span>Phân loại</span>
            <select value={form.category} onChange={set('category')}>
              <option value="">— Chọn phân loại (không bắt buộc) —</option>
              {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Tệp đính kèm (tối đa {MAX_FILES} tệp, mỗi tệp ≤ 10 MB)</span>
            <input type="file" multiple
              accept=".pdf,.png,.jpg,.jpeg,.txt,.docx"
              onChange={(e) => setFiles([...e.target.files])} />
            {files.length > 0 && (
              <small className="text-muted">{files.length} tệp: {files.map((f) => f.name).join(', ')}</small>
            )}
          </label>

          {formError && <p className="form-error" role="alert">{formError}</p>}

          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? 'Đang gửi…' : 'Gửi yêu cầu'}
          </button>
        </form>

        <p className="portal-foot">
          Đã có yêu cầu? <Link to="/track">Tra cứu trạng thái vé</Link> ·{' '}
          Nhân viên? <Link to="/login">Đăng nhập</Link>
        </p>
      </section>
    </div>
  );
}

function labelOfStatus(s) {
  return ({ OPEN: 'Mở', IN_PROGRESS: 'Đang xử lý', PENDING: 'Chờ bổ sung thông tin', RESOLVED: 'Đã giải quyết', CLOSED: 'Đã đóng' })[s] || s;
}
