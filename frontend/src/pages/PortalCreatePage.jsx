import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client.js';
import { CATEGORY_LABELS } from '../lib/labels.js';
import '../styles/portal.css';

// SRS 10.1 field rules (mirrored here for inline UX; backend is authoritative).
const MAX_FILES = 5;

function fieldErrors(err) {
  if (!err.details) return err.message;
  const parts = err.details.map((d) => {
    const field = (d.loc || []).filter((s) => typeof s === 'string').join('.');
    return field ? `${field}: ${d.msg}` : d.msg;
  });
  return parts.slice(0, 3).join('; ') || err.message;
}

function fmtBytes(b) {
  if (!b || b === 0) return '0 B';
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
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
  const [copied, setCopied] = useState(false);
  const fileInputRef = useRef(null);

  function set(key) {
    return (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  function handleFileChange(e) {
    const chosen = Array.from(e.target.files || []);
    if (files.length + chosen.length > MAX_FILES) {
      setFormError(`Mỗi yêu cầu tối đa ${MAX_FILES} tệp đính kèm.`);
      return;
    }
    setFiles((prev) => [...prev, ...chosen].slice(0, MAX_FILES));
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function removeFile(index) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  async function copyTicketCode(code) {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
    }
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
            <Link to="/" className="portal-nav-item active">Gửi yêu cầu</Link>
            <Link to="/track" className="portal-nav-item">Tra cứu tiến độ</Link>
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

      {/* --- Main Content Area --- */}
      <main className="portal-container">
        {created ? (
          /* --- Success View --- */
          <div className="portal-success-container">
            <section className="portal-success-card" role="status">
              <div className="portal-success-icon-wrap">
                ✓
              </div>
              <h1>Đã tiếp nhận yêu cầu hỗ trợ!</h1>
              <p>
                Cảm ơn <strong>{created.requester_name || 'quý khách'}</strong>, yêu cầu đã được đưa vào hệ thống xử lý. 
                Thông báo xác nhận và tiến độ xử lý sẽ được gửi tới email <strong>{created.requester_email || form.requester_email}</strong>.
              </p>

              <div className="portal-code-box">
                <span className="text-muted text-xs">Mã tra cứu:</span>
                <span className="portal-code" data-testid="created-code">{created.ticket_code}</span>
                <button
                  type="button"
                  className="btn-copy-code"
                  onClick={() => copyTicketCode(created.ticket_code)}
                  title="Sao chép mã tra cứu"
                >
                  {copied ? '✓ Đã sao chép' : 'Sao chép mã'}
                </button>
              </div>

              <p className="text-muted text-xs">
                Trạng thái hiện tại: <span className="badge badge--open">{labelOfStatus(created.status)}</span>
              </p>

              <div className="portal-actions">
                <Link className="btn-primary" to={`/track?code=${encodeURIComponent(created.ticket_code)}&email=${encodeURIComponent(created.requester_email || form.requester_email)}`}>
                  Tra cứu tiến độ vé ngay
                </Link>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    setCreated(null);
                    setForm({ requester_name: '', requester_email: '', subject: '', description: '', category: '' });
                    setFiles([]);
                  }}
                >
                  Gửi yêu cầu khác
                </button>
              </div>
            </section>
          </div>
        ) : (
          /* --- Two-Column Layout --- */
          <div className="portal-grid">
            {/* Cột trái: Hero Showcase & Cam kết chất lượng */}
            <div className="portal-hero-pane">
              <div className="portal-pill-badge">
                <span>✨</span> Cổng tiếp nhận hỗ trợ 24/7
              </div>

              <h1 className="portal-hero-title">
                Chúng tôi luôn sẵn sàng hỗ trợ bạn
              </h1>

              <p className="portal-hero-desc">
                Hãy mô tả chi tiết sự cố hoặc thắc mắc của bạn. Đội ngũ kỹ thuật viên kết hợp cùng Trợ lý AI sẽ tiếp nhận, phân loại và phản hồi qua email trong thời gian sớm nhất.
              </p>

              <div className="portal-features-list">
                <div className="portal-feature-item">
                  <div className="portal-feature-icon">⚡</div>
                  <div className="portal-feature-content">
                    <h3>Phân loại & Định tuyến tự động</h3>
                    <p>Trợ lý AI phân tích nội dung, định tuyến ngay tới đúng đội ngũ chuyên môn phụ trách.</p>
                  </div>
                </div>

                <div className="portal-feature-item">
                  <div className="portal-feature-icon">🔒</div>
                  <div className="portal-feature-content">
                    <h3>Bảo mật & Riêng tư tuyệt đối</h3>
                    <p>Thông tin liên hệ, nội dung trao đổi và tài liệu đính kèm được bảo vệ an toàn.</p>
                  </div>
                </div>

                <div className="portal-feature-item">
                  <div className="portal-feature-icon">🔍</div>
                  <div className="portal-feature-content">
                    <h3>Tra cứu tiến độ minh bạch</h3>
                    <p>Theo dõi trạng thái từng bước và nhận phản hồi chi tiết từ chuyên viên bằng mã vé.</p>
                  </div>
                </div>
              </div>

              {/* Thẻ tra cứu nhanh */}
              <div className="portal-quick-track-card">
                <div className="portal-quick-track-text">
                  <strong>Bạn đã gửi phiếu hỗ trợ trước đó?</strong><br />
                  Kiểm tra phản hồi mới nhất từ chuyên viên bằng mã vé của bạn.
                </div>
                <Link to="/track" className="portal-quick-track-link">
                  Tra cứu ngay →
                </Link>
              </div>
            </div>

            {/* Cột phải: Form gửi ticket cao cấp */}
            <div className="portal-form-card">
              <div className="portal-form-header">
                <h2>Gửi yêu cầu hỗ trợ mới</h2>
                <p>Điền đầy đủ thông tin bên dưới để chuyên viên xử lý chính xác nhất.</p>
              </div>

              <form onSubmit={handleSubmit} noValidate className="portal-form">
                <div className="form-row">
                  <label className="field">
                    <span>Họ và tên *</span>
                    <input
                      value={form.requester_name}
                      onChange={set('requester_name')}
                      required
                      minLength={2}
                      maxLength={100}
                      placeholder="Nguyễn Văn A"
                    />
                  </label>

                  <label className="field">
                    <span>Email nhận phản hồi *</span>
                    <input
                      type="email"
                      value={form.requester_email}
                      onChange={set('requester_email')}
                      required
                      maxLength={255}
                      placeholder="email@example.com"
                      autoComplete="email"
                    />
                  </label>
                </div>

                <div className="form-row">
                  <label className="field">
                    <span>Tiêu đề vấn đề *</span>
                    <input
                      value={form.subject}
                      onChange={set('subject')}
                      required
                      minLength={5}
                      maxLength={200}
                      placeholder="VD: Không thể đăng nhập vào hệ thống…"
                    />
                  </label>

                  <label className="field">
                    <span>Phân loại sự cố</span>
                    <select value={form.category} onChange={set('category')}>
                      <option value="">— Chọn danh mục (nếu có) —</option>
                      {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                        <option key={value} value={value}>{label}</option>
                      ))}
                    </select>
                  </label>
                </div>

                <label className="field">
                  <span>Mô tả chi tiết sự cố hoặc yêu cầu *</span>
                  <textarea
                    rows={5}
                    value={form.description}
                    onChange={set('description')}
                    required
                    minLength={10}
                    maxLength={20000}
                    placeholder="Mô tả cụ thể các bước dẫn đến lỗi, thông báo hiển thị trên màn hình, hoặc nội dung bạn cần hỗ trợ…"
                  />
                </label>

                {/* Khu vực tải tệp/ảnh đính kèm */}
                <div className="field">
                  <span>Tệp đính kèm hoặc ảnh chụp màn hình</span>
                  <div
                    className="file-upload-zone"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <span className="file-upload-icon">📁</span>
                    <span className="file-upload-label">
                      Bấm để chọn tệp hoặc ảnh minh họa
                    </span>
                    <span className="file-upload-hint">
                      Hỗ trợ PNG, JPG, WEBP, GIF, PDF, DOCX, TXT (tối đa {MAX_FILES} tệp, mỗi tệp ≤ 10 MB)
                    </span>
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      style={{ display: 'none' }}
                      accept=".pdf,.png,.jpg,.jpeg,.webp,.gif,.txt,.docx,image/*"
                      onChange={handleFileChange}
                    />
                  </div>

                  {files.length > 0 && (
                    <div className="selected-files-list">
                      {files.map((f, idx) => {
                        const isImg = f.type.startsWith('image/') || /\.(png|jpe?g|webp|gif)$/i.test(f.name);
                        return (
                          <div key={idx} className="selected-file-chip">
                            <span>{isImg ? '🖼️' : '📎'} {f.name}</span>
                            <span className="text-muted text-xs">({fmtBytes(f.size)})</span>
                            <button
                              type="button"
                              onClick={() => removeFile(idx)}
                              title="Xóa tệp này"
                              aria-label="Xóa tệp"
                            >
                              ✕
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {formError && (
                  <p className="form-error" role="alert" style={{ margin: 0 }}>
                    ⚠ {formError}
                  </p>
                )}

                <button
                  type="submit"
                  className="btn-primary btn-submit-ticket"
                  disabled={submitting}
                >
                  {submitting ? (
                    'Đang gửi yêu cầu…'
                  ) : (
                    <>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="22" y1="2" x2="11" y2="13" />
                        <polygon points="22 2 15 22 11 13 2 9 22 2" />
                      </svg>
                      Gửi yêu cầu hỗ trợ ngay
                    </>
                  )}
                </button>
              </form>
            </div>
          </div>
        )}
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
