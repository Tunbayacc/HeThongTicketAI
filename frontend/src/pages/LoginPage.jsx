import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { landingFor, useAuth } from '../auth/AuthContext.jsx';
import '../styles/auth.css';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) return; // disable double-submit (SRS 7.1.1)
    setSubmitting(true);
    setFormError(null);
    try {
      const user = await login(email, password);
      navigate(landingFor(user.role), { replace: true }); // FR-AUTH-09
    } catch (err) {
      if (err.error_code === 'AUTH_ACCOUNT_LOCKED') {
        setFormError('Tài khoản đã bị khóa tạm thời do đăng nhập sai nhiều lần. Vui lòng thử lại sau.');
      } else if (err.error_code === 'AUTH_INVALID_CREDENTIALS') {
        setFormError('Email hoặc mật khẩu không đúng.');
      } else {
        setFormError(err.message || 'Không thể đăng nhập. Vui lòng thử lại.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <div className="login-brand">
          <span className="login-brand-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5Z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
            </svg>
          </span>
          <div>
            <h1 className="login-title">Đăng nhập</h1>
            <p className="text-muted text-sm" style={{ margin: 0 }}>Hệ thống hỗ trợ khách hàng</p>
          </div>
        </div>

        <label className="field">
          <span>Email</span>
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="ten@example.com"
          />
        </label>

        <label className="field">
          <span>Mật khẩu</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={1}
          />
        </label>

        {formError && <p className="form-error" role="alert">{formError}</p>}

        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? 'Đang đăng nhập…' : 'Đăng nhập'}
        </button>

        <Link to="/" className="back-link">← Quay lại trang chủ</Link>
      </form>
    </div>
  );
}
