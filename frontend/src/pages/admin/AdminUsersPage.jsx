import { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client.js';
import { ROLE_LABELS, fmtDate, labelOf } from '../../lib/labels.js';

export default function AdminUsersPage() {
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState({ full_name: '', email: '', password: '', role: 'AGENT' });
  const [createError, setCreateError] = useState(null);
  const [createSubmitting, setCreateSubmitting] = useState(false);

  const [editingUser, setEditingUser] = useState(null);
  const [editForm, setEditForm] = useState({ full_name: '', role: 'AGENT', password: '' });
  const [editError, setEditError] = useState(null);
  const [editSubmitting, setEditSubmitting] = useState(false);

  const [deactivatingUser, setDeactivatingUser] = useState(null);
  const [deactivateError, setDeactivateError] = useState(null);
  const [deactivateSubmitting, setDeactivateSubmitting] = useState(false);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: '15' });
      if (search.trim()) params.set('q', search.trim());
      if (roleFilter) params.set('role', roleFilter);

      const data = await api.get(`/api/users?${params.toString()}`);
      setUsers(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      setError(err.message || 'Không thể tải danh sách tài khoản người dùng.');
    } finally {
      setLoading(false);
    }
  }, [page, search, roleFilter]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // Handle Create User
  async function handleCreateSubmit(e) {
    e.preventDefault();
    setCreateSubmitting(true);
    setCreateError(null);
    try {
      await api.post('/api/users', createForm);
      setShowCreateModal(false);
      setCreateForm({ full_name: '', email: '', password: '', role: 'AGENT' });
      fetchUsers();
    } catch (err) {
      setCreateError(err.message || 'Không thể tạo tài khoản người dùng.');
    } finally {
      setCreateSubmitting(false);
    }
  }

  // Handle Edit User
  function openEditModal(u) {
    setEditingUser(u);
    setEditForm({ full_name: u.full_name, role: u.role, password: '' });
    setEditError(null);
  }

  async function handleEditSubmit(e) {
    e.preventDefault();
    setEditSubmitting(true);
    setEditError(null);
    try {
      const payload = { full_name: editForm.full_name, role: editForm.role };
      if (editForm.password.trim()) {
        payload.password = editForm.password.trim();
      }
      await api.patch(`/api/users/${editingUser.id}`, payload);
      setEditingUser(null);
      fetchUsers();
    } catch (err) {
      setEditError(err.message || 'Không thể cập nhật thông tin người dùng.');
    } finally {
      setEditSubmitting(false);
    }
  }

  // Handle Deactivate / Activate Toggle
  async function handleToggleActive(u) {
    setDeactivateSubmitting(true);
    setDeactivateError(null);
    try {
      await api.patch(`/api/users/${u.id}`, { is_active: !u.is_active });
      setDeactivatingUser(null);
      fetchUsers();
    } catch (err) {
      setDeactivateError(err.message || 'Không thể thay đổi trạng thái người dùng.');
    } finally {
      setDeactivateSubmitting(false);
    }
  }

  // Summary counts from loaded users
  const activeCount = users.filter((u) => u.is_active).length;
  const agentCount = users.filter((u) => u.role === 'AGENT').length;
  const managerCount = users.filter((u) => u.role === 'MANAGER').length;
  const adminCount = users.filter((u) => u.role === 'ADMIN').length;

  return (
    <div className="admin-page-container">
      {/* Top KPI Summary Cards */}
      <div className="admin-summary-grid">
        <div className="admin-kpi-card">
          <div className="admin-kpi-content">
            <span className="admin-kpi-val">{total}</span>
            <span className="admin-kpi-lbl">Tổng tài khoản hệ thống</span>
          </div>
          <div className="admin-kpi-icon admin-kpi-icon--blue">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
          </div>
        </div>

        <div className="admin-kpi-card">
          <div className="admin-kpi-content">
            <span className="admin-kpi-val" style={{ color: 'var(--color-success)' }}>
              {activeCount}
            </span>
            <span className="admin-kpi-lbl">Đang hoạt động trên trang</span>
          </div>
          <div className="admin-kpi-icon admin-kpi-icon--green">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          </div>
        </div>

        <div className="admin-kpi-card">
          <div className="admin-kpi-content">
            <span className="admin-kpi-val" style={{ color: 'var(--color-primary)' }}>
              {agentCount}
            </span>
            <span className="admin-kpi-lbl">Nhân viên hỗ trợ (Agent)</span>
          </div>
          <div className="admin-kpi-icon admin-kpi-icon--blue">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
        </div>

        <div className="admin-kpi-card">
          <div className="admin-kpi-content">
            <span className="admin-kpi-val" style={{ color: '#7c3aed' }}>
              {managerCount + adminCount}
            </span>
            <span className="admin-kpi-lbl">Quản lý & Quản trị viên</span>
          </div>
          <div className="admin-kpi-icon admin-kpi-icon--purple">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
        </div>
      </div>

      {/* Controls & Search Toolbar */}
      <div className="admin-toolbar">
        <div className="admin-filters">
          <div className="admin-search-wrap">
            <span className="admin-search-icon">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </span>
            <input
              type="text"
              className="admin-input"
              style={{ width: '100%', paddingLeft: 34, paddingRight: search ? 28 : 12 }}
              placeholder="Tìm theo tên, email tài khoản…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
            {search && (
              <button
                type="button"
                className="admin-search-clear"
                onClick={() => { setSearch(''); setPage(1); }}
                title="Xóa tìm kiếm"
              >
                ✕
              </button>
            )}
          </div>

          <select
            className="admin-select"
            value={roleFilter}
            onChange={(e) => {
              setRoleFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Tất cả vai trò</option>
            <option value="AGENT">Nhân viên hỗ trợ (Agent)</option>
            <option value="MANAGER">Quản lý nhóm (Manager)</option>
            <option value="ADMIN">Quản trị viên (Admin)</option>
          </select>
        </div>

        <button
          type="button"
          className="btn-primary"
          onClick={() => {
            setCreateError(null);
            setShowCreateModal(true);
          }}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Thêm người dùng mới
        </button>
      </div>

      {error && <div className="alert-error" style={{ marginBottom: 'var(--space-3)' }}>{error}</div>}

      {loading ? (
        <div className="state-loading">Đang tải danh sách tài khoản người dùng…</div>
      ) : users.length === 0 ? (
        <div className="empty-state">
          <p style={{ margin: 0 }}>Không tìm thấy tài khoản người dùng nào phù hợp với bộ lọc.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <div style={{ overflowX: 'auto' }}>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>NGƯỜI DÙNG</th>
                  <th>VAI TRÒ HỆ THỐNG</th>
                  <th>TRẠNG THÁI</th>
                  <th>NGÀY TẠO</th>
                  <th style={{ textAlign: 'right' }}>THAO TÁC</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const roleClass = `user-avatar-${u.role.toLowerCase()}`;
                  const initial = (u.full_name || u.email || '?').charAt(0).toUpperCase();

                  return (
                    <tr key={u.id}>
                      <td>
                        <div className="user-identity-cell">
                          <span className={`user-avatar-sm ${roleClass}`}>
                            {initial}
                          </span>
                          <div className="user-identity-info">
                            <span className="user-identity-name">{u.full_name}</span>
                            <span className="user-identity-email">{u.email}</span>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className={`badge badge-${u.role.toLowerCase()}`}>
                          {labelOf(ROLE_LABELS, u.role)}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${u.is_active ? 'badge-active' : 'badge-inactive'}`}>
                          <span className={`status-dot ${u.is_active ? 'status-dot-active' : 'status-dot-inactive'}`} />
                          {u.is_active ? 'Đang hoạt động' : 'Đã vô hiệu hóa'}
                        </span>
                      </td>
                      <td style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-xs)' }}>
                        {fmtDate(u.created_at)}
                      </td>
                      <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                        <button
                          type="button"
                          className="btn-secondary btn-sm"
                          style={{ marginRight: 'var(--space-2)' }}
                          onClick={() => openEditModal(u)}
                        >
                          Chỉnh sửa
                        </button>
                        <button
                          type="button"
                          className={u.is_active ? 'btn-danger btn-sm' : 'btn-secondary btn-sm'}
                          onClick={() => setDeactivatingUser(u)}
                        >
                          {u.is_active ? 'Vô hiệu hóa' : 'Kích hoạt'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="admin-pagination">
            <span>Tổng cộng: {total} người dùng · Trang {page} / {totalPages}</span>
            <div className="admin-pagination-controls">
              <button
                type="button"
                className="btn-secondary btn-sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                ‹ Trang trước
              </button>
              <button
                type="button"
                className="btn-secondary btn-sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Trang sau ›
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Tạo tài khoản người dùng */}
      {showCreateModal && (
        <div className="admin-modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div className="admin-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2 className="admin-modal-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <line x1="19" y1="8" x2="19" y2="14" />
                  <line x1="22" y1="11" x2="16" y2="11" />
                </svg>
                Tạo tài khoản người dùng mới
              </h2>
              <button type="button" className="admin-modal-close" onClick={() => setShowCreateModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateSubmit}>
              <div className="admin-modal-body">
                {createError && <div className="alert-error">{createError}</div>}
                
                <div className="form-group">
                  <label className="form-label">Họ và tên *</label>
                  <input
                    type="text"
                    required
                    className="admin-input"
                    placeholder="VD: Nguyễn Văn An"
                    value={createForm.full_name}
                    onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Email đăng nhập *</label>
                  <input
                    type="email"
                    required
                    className="admin-input"
                    placeholder="an.nguyen@example.com"
                    value={createForm.email}
                    onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Mật khẩu khởi tạo *</label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    className="admin-input"
                    placeholder="Tối thiểu 8 ký tự"
                    value={createForm.password}
                    onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                  />
                  <span className="form-hint">Mật khẩu nên chứa ít nhất 8 ký tự, bao gồm chữ và số.</span>
                </div>

                <div className="form-group">
                  <label className="form-label">Vai trò hệ thống *</label>
                  <select
                    className="admin-select"
                    value={createForm.role}
                    onChange={(e) => setCreateForm({ ...createForm, role: e.target.value })}
                  >
                    <option value="AGENT">Nhân viên hỗ trợ — Xử lý và phản hồi vé của khách hàng</option>
                    <option value="MANAGER">Quản lý nhóm — Phân công vé, theo dõi SLA và nhóm</option>
                    <option value="ADMIN">Quản trị viên — Toàn quyền cấu hình người dùng, đội ngũ, SLA</option>
                  </select>
                </div>
              </div>
              <div className="admin-modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setShowCreateModal(false)}>Hủy bỏ</button>
                <button type="submit" className="btn-primary" disabled={createSubmitting}>
                  {createSubmitting ? 'Đang tạo…' : 'Xác nhận tạo người dùng'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Chỉnh sửa thông tin người dùng */}
      {editingUser && (
        <div className="admin-modal-backdrop" onClick={() => setEditingUser(null)}>
          <div className="admin-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2 className="admin-modal-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
                Cập nhật tài khoản: {editingUser.email}
              </h2>
              <button type="button" className="admin-modal-close" onClick={() => setEditingUser(null)}>✕</button>
            </div>
            <form onSubmit={handleEditSubmit}>
              <div className="admin-modal-body">
                {editError && <div className="alert-error">{editError}</div>}
                
                <div className="form-group">
                  <label className="form-label">Họ và tên *</label>
                  <input
                    type="text"
                    required
                    className="admin-input"
                    value={editForm.full_name}
                    onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Vai trò hệ thống *</label>
                  <select
                    className="admin-select"
                    value={editForm.role}
                    onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                  >
                    <option value="AGENT">Nhân viên hỗ trợ (Support Agent)</option>
                    <option value="MANAGER">Quản lý nhóm (Team Manager)</option>
                    <option value="ADMIN">Quản trị viên (Administrator)</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Đổi mật khẩu mới (để trống nếu không đổi)</label>
                  <input
                    type="password"
                    minLength={8}
                    className="admin-input"
                    placeholder="Nhập mật khẩu mới (tối thiểu 8 ký tự)"
                    value={editForm.password}
                    onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
                  />
                </div>
              </div>
              <div className="admin-modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setEditingUser(null)}>Hủy bỏ</button>
                <button type="submit" className="btn-primary" disabled={editSubmitting}>
                  {editSubmitting ? 'Đang lưu…' : 'Lưu thay đổi'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Xác nhận vô hiệu hóa / kích hoạt lại */}
      {deactivatingUser && (
        <div className="admin-modal-backdrop" onClick={() => setDeactivatingUser(null)}>
          <div className="admin-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2 className="admin-modal-title">
                {deactivatingUser.is_active ? 'Xác nhận vô hiệu hóa tài khoản' : 'Xác nhận kích hoạt lại tài khoản'}
              </h2>
              <button type="button" className="admin-modal-close" onClick={() => setDeactivatingUser(null)}>✕</button>
            </div>
            <div className="admin-modal-body">
              {deactivateError && <div className="alert-error">{deactivateError}</div>}
              <p style={{ margin: 0, lineHeight: 1.5 }}>
                Bạn có chắc chắn muốn {deactivatingUser.is_active ? 'vô hiệu hóa' : 'kích hoạt lại'} tài khoản của{' '}
                <strong>{deactivatingUser.full_name}</strong> ({deactivatingUser.email})?
              </p>
              {deactivatingUser.is_active && (
                <div className="alert-warning" style={{ marginTop: 'var(--space-2)', fontSize: 'var(--font-size-xs)' }}>
                  ⚠️ Khi vô hiệu hóa, tài khoản này sẽ không thể đăng nhập vào hệ thống. Các vé đang mở phụ trách bởi người này sẽ được đánh dấu <strong>Cần phân công lại</strong>.
                </div>
              )}
            </div>
            <div className="admin-modal-footer">
              <button type="button" className="btn-secondary" onClick={() => setDeactivatingUser(null)}>Hủy bỏ</button>
              <button
                type="button"
                className={deactivatingUser.is_active ? 'btn-danger' : 'btn-primary'}
                disabled={deactivateSubmitting}
                onClick={() => handleToggleActive(deactivatingUser)}
              >
                {deactivateSubmitting
                  ? 'Đang xử lý…'
                  : deactivatingUser.is_active
                  ? 'Vô hiệu hóa tài khoản'
                  : 'Kích hoạt lại'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
