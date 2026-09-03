import { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client.js';

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
      setError(err.message || 'Không thể tải danh sách người dùng.');
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
      setCreateError(err.message || 'Không thể tạo người dùng.');
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
      setEditError(err.message || 'Không thể cập nhật người dùng.');
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

  return (
    <div>
      <div className="admin-toolbar">
        <div className="admin-filters">
          <input
            type="text"
            className="admin-input"
            placeholder="Tìm theo tên, email..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
          <select
            className="admin-select"
            value={roleFilter}
            onChange={(e) => {
              setRoleFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Tất cả vai trò</option>
            <option value="AGENT">Support Agent</option>
            <option value="MANAGER">Team Manager</option>
            <option value="ADMIN">Administrator</option>
          </select>
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={() => setShowCreateModal(true)}
        >
          + Tạo người dùng
        </button>
      </div>

      {error && <div className="alert-error" style={{ marginBottom: 'var(--space-3)' }}>{error}</div>}

      {loading ? (
        <div className="state-loading">Đang tải danh sách người dùng...</div>
      ) : users.length === 0 ? (
        <div className="state-empty">Không tìm thấy người dùng phù hợp.</div>
      ) : (
        <>
          <div className="admin-table-container">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Họ tên</th>
                  <th>Email</th>
                  <th>Vai trò</th>
                  <th>Trạng thái</th>
                  <th>Ngày tạo</th>
                  <th style={{ textAlign: 'right' }}>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td style={{ fontWeight: 600 }}>{u.full_name}</td>
                    <td>{u.email}</td>
                    <td>
                      <span className={`badge badge-${u.role.toLowerCase()}`}>
                        {u.role}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${u.is_active ? 'badge-active' : 'badge-inactive'}`}>
                        {u.is_active ? 'Hoạt động' : 'Vô hiệu hóa'}
                      </span>
                    </td>
                    <td>{new Date(u.created_at).toLocaleDateString('vi-VN')}</td>
                    <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <button
                        type="button"
                        className="btn-secondary btn-sm"
                        style={{ marginRight: 'var(--space-2)' }}
                        onClick={() => openEditModal(u)}
                      >
                        Sửa
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
                ))}
              </tbody>
            </table>
          </div>

          <div className="admin-pagination">
            <span>Tổng cộng: {total} người dùng</span>
            <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
              <button
                type="button"
                className="btn-secondary btn-sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Trước
              </button>
              <span style={{ padding: '0 var(--space-2)', alignSelf: 'center' }}>
                Trang {page} / {totalPages}
              </span>
              <button
                type="button"
                className="btn-secondary btn-sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Sau
              </button>
            </div>
          </div>
        </>
      )}

      {/* Modal: Create User */}
      {showCreateModal && (
        <div className="admin-modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div className="admin-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2 className="admin-modal-title">Tạo tài khoản người dùng</h2>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setShowCreateModal(false)}>✕</button>
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
                    value={createForm.email}
                    onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Mật khẩu khởi tạo * (tối thiểu 8 ký tự)</label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    className="admin-input"
                    value={createForm.password}
                    onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Vai trò hệ thống *</label>
                  <select
                    className="admin-select"
                    value={createForm.role}
                    onChange={(e) => setCreateForm({ ...createForm, role: e.target.value })}
                  >
                    <option value="AGENT">Support Agent (Nhân viên)</option>
                    <option value="MANAGER">Team Manager (Quản lý nhóm)</option>
                    <option value="ADMIN">Administrator (Quản trị viên)</option>
                  </select>
                </div>
              </div>
              <div className="admin-modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setShowCreateModal(false)}>Hủy</button>
                <button type="submit" className="btn-primary" disabled={createSubmitting}>
                  {createSubmitting ? 'Đang tạo...' : 'Tạo người dùng'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Edit User */}
      {editingUser && (
        <div className="admin-modal-backdrop" onClick={() => setEditingUser(null)}>
          <div className="admin-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2 className="admin-modal-title">Cập nhật thông tin: {editingUser.email}</h2>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setEditingUser(null)}>✕</button>
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
                  <label className="form-label">Vai trò *</label>
                  <select
                    className="admin-select"
                    value={editForm.role}
                    onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                  >
                    <option value="AGENT">Support Agent</option>
                    <option value="MANAGER">Team Manager</option>
                    <option value="ADMIN">Administrator</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Đổi mật khẩu mới (để trống nếu không đổi)</label>
                  <input
                    type="password"
                    minLength={8}
                    className="admin-input"
                    placeholder="Mật khẩu mới (tối thiểu 8 ký tự)"
                    value={editForm.password}
                    onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
                  />
                </div>
              </div>
              <div className="admin-modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setEditingUser(null)}>Hủy</button>
                <button type="submit" className="btn-primary" disabled={editSubmitting}>
                  {editSubmitting ? 'Đang lưu...' : 'Lưu thay đổi'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Confirmation Dialog: Toggle Active */}
      {deactivatingUser && (
        <div className="admin-modal-backdrop" onClick={() => setDeactivatingUser(null)}>
          <div className="admin-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2 className="admin-modal-title">
                {deactivatingUser.is_active ? 'Xác nhận vô hiệu hóa' : 'Xác nhận kích hoạt lại'}
              </h2>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setDeactivatingUser(null)}>✕</button>
            </div>
            <div className="admin-modal-body">
              {deactivateError && <div className="alert-error">{deactivateError}</div>}
              <p>
                Bạn có chắc chắn muốn {deactivatingUser.is_active ? 'vô hiệu hóa tài khoản' : 'kích hoạt lại tài khoản'}{' '}
                <strong>{deactivatingUser.full_name}</strong> ({deactivatingUser.email})?
              </p>
              {deactivatingUser.is_active && (
                <p className="form-hint" style={{ color: 'var(--color-danger)' }}>
                  ⚠️ Khi vô hiệu hóa, tài khoản này sẽ không thể đăng nhập và các vé đang mở phụ trách sẽ được đánh dấu cần phân công lại.
                </p>
              )}
            </div>
            <div className="admin-modal-footer">
              <button type="button" className="btn-secondary" onClick={() => setDeactivatingUser(null)}>Hủy</button>
              <button
                type="button"
                className={deactivatingUser.is_active ? 'btn-danger' : 'btn-primary'}
                disabled={deactivateSubmitting}
                onClick={() => handleToggleActive(deactivatingUser)}
              >
                {deactivateSubmitting ? 'Đang xử lý...' : (deactivatingUser.is_active ? 'Vô hiệu hóa' : 'Kích hoạt')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
