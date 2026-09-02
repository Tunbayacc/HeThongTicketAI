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
        <h1 className="login-title">Đăng nhập</h1>
        <p className="text-muted">Hệ thống hỗ trợ khách hàng</p>

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
