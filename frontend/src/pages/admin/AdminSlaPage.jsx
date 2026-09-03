import { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client.js';

const PRIORITIES = [
  { value: 'URGENT', label: 'Khẩn cấp (URGENT)', color: '#dc2626' },
  { value: 'HIGH', label: 'Cao (HIGH)', color: '#ea580c' },
  { value: 'MEDIUM', label: 'Trung bình (MEDIUM)', color: '#d97706' },
  { value: 'LOW', label: 'Thấp (LOW)', color: '#2563eb' },
];

function formatMinutes(mins) {
  if (!mins && mins !== 0) return '—';
  if (mins < 60) return `${mins} phút`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m === 0 ? `${h} giờ` : `${h} giờ ${m} phút`;
}

export default function AdminSlaPage() {
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState({
    name: '',
    priority: 'URGENT',
    first_response_minutes: 15,
    resolution_minutes: 240,
    pause_on_pending: false,
    effective_from: new Date().toISOString().slice(0, 16),
    effective_to: '',
    is_active: true,
  });
  const [createError, setCreateError] = useState(null);
  const [createSubmitting, setCreateSubmitting] = useState(false);

  const [editingPolicy, setEditingPolicy] = useState(null);
  const [editForm, setEditForm] = useState({
    name: '',
    first_response_minutes: 60,
    resolution_minutes: 480,
    pause_on_pending: false,
    effective_from: '',
    effective_to: '',
    is_active: true,
  });
  const [editError, setEditError] = useState(null);
  const [editSubmitting, setEditSubmitting] = useState(false);

  const fetchPolicies = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get('/api/sla-policies');
      setPolicies(data);
    } catch (err) {
      setError(err.message || 'Không thể tải danh sách chính sách SLA.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPolicies();
  }, [fetchPolicies]);

  // Handle Create SLA Policy
  async function handleCreateSubmit(e) {
    e.preventDefault();
    setCreateSubmitting(true);
    setCreateError(null);
    try {
      const payload = {
        name: createForm.name.trim(),
        priority: createForm.priority,
        first_response_minutes: Number(createForm.first_response_minutes),
        resolution_minutes: Number(createForm.resolution_minutes),
        pause_on_pending: Boolean(createForm.pause_on_pending),
        effective_from: new Date(createForm.effective_from).toISOString(),
        effective_to: createForm.effective_to ? new Date(createForm.effective_to).toISOString() : null,
        is_active: Boolean(createForm.is_active),
      };

      await api.post('/api/sla-policies', payload);
      setShowCreateModal(false);
      fetchPolicies();
    } catch (err) {
      if (err.error_code === 'SLA_POLICY_CONFLICT') {
        setCreateError(`⚠️ Chồng lấn thời gian hiệu lực: ${err.message}`);
      } else {
        setCreateError(err.message || 'Không thể tạo chính sách SLA.');
      }
    } finally {
      setCreateSubmitting(false);
    }
  }

  // Handle Edit SLA Policy
  function openEditModal(p) {
    setEditingPolicy(p);
    setEditForm({
      name: p.name,
      first_response_minutes: p.first_response_minutes,
      resolution_minutes: p.resolution_minutes,
      pause_on_pending: p.pause_on_pending,
      effective_from: p.effective_from ? new Date(p.effective_from).toISOString().slice(0, 16) : '',
      effective_to: p.effective_to ? new Date(p.effective_to).toISOString().slice(0, 16) : '',
      is_active: p.is_active,
    });
    setEditError(null);
  }

  async function handleEditSubmit(e) {
    e.preventDefault();
    setEditSubmitting(true);
    setEditError(null);
    try {
      const payload = {
        name: editForm.name.trim(),
        first_response_minutes: Number(editForm.first_response_minutes),
        resolution_minutes: Number(editForm.resolution_minutes),
        pause_on_pending: Boolean(editForm.pause_on_pending),
        effective_from: editForm.effective_from ? new Date(editForm.effective_from).toISOString() : null,
        effective_to: editForm.effective_to ? new Date(editForm.effective_to).toISOString() : null,
        is_active: Boolean(editForm.is_active),
      };

      await api.patch(`/api/sla-policies/${editingPolicy.id}`, payload);
      setEditingPolicy(null);
      fetchPolicies();
    } catch (err) {
      if (err.error_code === 'SLA_POLICY_CONFLICT') {
        setEditError(`⚠️ Chồng lấn thời gian hiệu lực: ${err.message}`);
      } else {
        setEditError(err.message || 'Không thể cập nhật chính sách SLA.');
      }
    } finally {
      setEditSubmitting(false);
    }
  }

  return (
    <div>
      <div className="admin-toolbar">
        <div>
          <h2 style={{ margin: 0, fontSize: '1.2rem' }}>Chính sách cam kết dịch vụ (SLA)</h2>
          <p className="admin-subtitle">
            Quy định thời hạn phản hồi đầu tiên và thời hạn giải quyết vé theo mức độ ưu tiên
          </p>
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={() => {
            setCreateError(null);
            setShowCreateModal(true);
          }}
        >
          + Thêm chính sách SLA
        </button>
      </div>

      {error && <div className="alert-error" style={{ marginBottom: 'var(--space-3)' }}>{error}</div>}

      {loading ? (
        <div className="state-loading">Đang tải danh sách chính sách SLA...</div>
      ) : policies.length === 0 ? (
        <div className="state-empty">Chưa có chính sách SLA nào.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
          {PRIORITIES.map((pGroup) => {
            const groupPolicies = policies.filter((p) => p.priority === pGroup.value);
            return (
              <div key={pGroup.value} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                  <span
                    style={{
                      display: 'inline-block',
                      width: 10,
                      height: 10,
                      borderRadius: '50%',
                      backgroundColor: pGroup.color,
                    }}
                  />
                  <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>{pGroup.label}</h3>
                  <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                    ({groupPolicies.length} chính sách)
                  </span>
                </div>

                <div className="admin-card-grid">
                  {groupPolicies.map((p) => (
                    <div
                      key={p.id}
                      className="admin-card"
                      style={{
                        borderLeft: `4px solid ${p.is_active ? pGroup.color : 'var(--color-border)'}`,
                        opacity: p.is_active ? 1 : 0.75,
                      }}
                    >
                      <div className="admin-card-header">
                        <strong className="admin-card-title">{p.name}</strong>
                        <span className={`badge ${p.is_active ? 'badge-active' : 'badge-inactive'}`}>
                          {p.is_active ? 'Đang hiệu lực' : 'Hết hiệu lực'}
                        </span>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-2)', marginTop: 'var(--space-1)' }}>
                        <div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Phản hồi đầu tiên</div>
                          <div style={{ fontWeight: 600, fontSize: '1rem' }}>{formatMinutes(p.first_response_minutes)}</div>
                        </div>
                        <div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Giải quyết xong</div>
                          <div style={{ fontWeight: 600, fontSize: '1rem' }}>{formatMinutes(p.resolution_minutes)}</div>
                        </div>
                      </div>

                      <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: 'var(--space-1)' }}>
                        <div>
                          Tạm dừng khi chờ (Pending):{' '}
                          <strong>{p.pause_on_pending ? 'Có' : 'Không'}</strong>
                        </div>
                        <div>
                          Hiệu lực từ:{' '}
                          <strong>{new Date(p.effective_from).toLocaleDateString('vi-VN')}</strong>
                          {p.effective_to ? (
                            <> đến <strong>{new Date(p.effective_to).toLocaleDateString('vi-VN')}</strong></>
                          ) : (
                            ' (vô thời hạn)'
                          )}
                        </div>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'var(--space-2)' }}>
                        <button
                          type="button"
                          className="btn-secondary btn-sm"
                          onClick={() => openEditModal(p)}
                        >
                          Chỉnh sửa
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Modal: Create SLA Policy */}
      {showCreateModal && (
        <div className="admin-modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div className="admin-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2 className="admin-modal-title">Tạo chính sách SLA mới</h2>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setShowCreateModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateSubmit}>
              <div className="admin-modal-body">
                {createError && <div className="alert-error">{createError}</div>}
                <div className="form-group">
                  <label className="form-label">Tên chính sách *</label>
                  <input
                    type="text"
                    required
                    className="admin-input"
                    placeholder="VD: SLA Khẩn cấp Q4/2026"
                    value={createForm.name}
                    onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Mức độ ưu tiên áp dụng *</label>
                  <select
                    className="admin-select"
                    value={createForm.priority}
                    onChange={(e) => setCreateForm({ ...createForm, priority: e.target.value })}
                  >
                    <option value="URGENT">Khẩn cấp (URGENT)</option>
                    <option value="HIGH">Cao (HIGH)</option>
                    <option value="MEDIUM">Trung bình (MEDIUM)</option>
                    <option value="LOW">Thấp (LOW)</option>
                  </select>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                  <div className="form-group">
                    <label className="form-label">Phản hồi (phút) *</label>
                    <input
                      type="number"
                      required
                      min={1}
                      className="admin-input"
                      value={createForm.first_response_minutes}
                      onChange={(e) => setCreateForm({ ...createForm, first_response_minutes: e.target.value })}
                    />
                    <span className="form-hint">{formatMinutes(Number(createForm.first_response_minutes))}</span>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Giải quyết (phút) *</label>
                    <input
                      type="number"
                      required
                      min={1}
                      className="admin-input"
                      value={createForm.resolution_minutes}
                      onChange={(e) => setCreateForm({ ...createForm, resolution_minutes: e.target.value })}
                    />
                    <span className="form-hint">{formatMinutes(Number(createForm.resolution_minutes))}</span>
                  </div>
                </div>

                <div className="form-group" style={{ flexDirection: 'row', alignItems: 'center', gap: 'var(--space-2)' }}>
                  <input
                    type="checkbox"
                    id="create-pause-toggle"
                    checked={createForm.pause_on_pending}
                    onChange={(e) => setCreateForm({ ...createForm, pause_on_pending: e.target.checked })}
                  />
                  <label htmlFor="create-pause-toggle" className="form-label" style={{ cursor: 'pointer' }}>
                    Tạm dừng tính hạn khi vé ở trạng thái Chờ (Pending)
                  </label>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                  <div className="form-group">
                    <label className="form-label">Hiệu lực từ *</label>
                    <input
                      type="datetime-local"
                      required
                      className="admin-input"
                      value={createForm.effective_from}
                      onChange={(e) => setCreateForm({ ...createForm, effective_from: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Hiệu lực đến (tùy chọn)</label>
                    <input
                      type="datetime-local"
                      className="admin-input"
                      value={createForm.effective_to}
                      onChange={(e) => setCreateForm({ ...createForm, effective_to: e.target.value })}
                    />
                  </div>
                </div>

                <div className="form-group" style={{ flexDirection: 'row', alignItems: 'center', gap: 'var(--space-2)' }}>
                  <input
                    type="checkbox"
                    id="create-active-toggle"
                    checked={createForm.is_active}
                    onChange={(e) => setCreateForm({ ...createForm, is_active: e.target.checked })}
                  />
                  <label htmlFor="create-active-toggle" className="form-label" style={{ cursor: 'pointer' }}>
                    Kích hoạt ngay
                  </label>
                </div>
              </div>
              <div className="admin-modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setShowCreateModal(false)}>Hủy</button>
                <button type="submit" className="btn-primary" disabled={createSubmitting}>
                  {createSubmitting ? 'Đang tạo...' : 'Tạo chính sách'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Edit SLA Policy */}
      {editingPolicy && (
        <div className="admin-modal-backdrop" onClick={() => setEditingPolicy(null)}>
          <div className="admin-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2 className="admin-modal-title">Chỉnh sửa: {editingPolicy.name}</h2>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setEditingPolicy(null)}>✕</button>
            </div>
            <form onSubmit={handleEditSubmit}>
              <div className="admin-modal-body">
                {editError && <div className="alert-error">{editError}</div>}
                <div className="form-group">
                  <label className="form-label">Tên chính sách *</label>
                  <input
                    type="text"
                    required
                    className="admin-input"
                    value={editForm.name}
                    onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                  <div className="form-group">
                    <label className="form-label">Phản hồi (phút) *</label>
                    <input
                      type="number"
                      required
                      min={1}
                      className="admin-input"
                      value={editForm.first_response_minutes}
                      onChange={(e) => setEditForm({ ...editForm, first_response_minutes: e.target.value })}
                    />
                    <span className="form-hint">{formatMinutes(Number(editForm.first_response_minutes))}</span>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Giải quyết (phút) *</label>
                    <input
                      type="number"
                      required
                      min={1}
                      className="admin-input"
                      value={editForm.resolution_minutes}
                      onChange={(e) => setEditForm({ ...editForm, resolution_minutes: e.target.value })}
                    />
                    <span className="form-hint">{formatMinutes(Number(editForm.resolution_minutes))}</span>
                  </div>
                </div>

                <div className="form-group" style={{ flexDirection: 'row', alignItems: 'center', gap: 'var(--space-2)' }}>
                  <input
                    type="checkbox"
                    id="edit-pause-toggle"
                    checked={editForm.pause_on_pending}
                    onChange={(e) => setEditForm({ ...editForm, pause_on_pending: e.target.checked })}
                  />
                  <label htmlFor="edit-pause-toggle" className="form-label" style={{ cursor: 'pointer' }}>
                    Tạm dừng tính hạn khi vé ở trạng thái Chờ (Pending)
                  </label>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                  <div className="form-group">
                    <label className="form-label">Hiệu lực từ</label>
                    <input
                      type="datetime-local"
                      className="admin-input"
                      value={editForm.effective_from}
                      onChange={(e) => setEditForm({ ...editForm, effective_from: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Hiệu lực đến (để trống nếu vô thời hạn)</label>
                    <input
                      type="datetime-local"
                      className="admin-input"
                      value={editForm.effective_to}
                      onChange={(e) => setEditForm({ ...editForm, effective_to: e.target.value })}
                    />
                  </div>
                </div>

                <div className="form-group" style={{ flexDirection: 'row', alignItems: 'center', gap: 'var(--space-2)' }}>
                  <input
                    type="checkbox"
                    id="edit-active-toggle"
                    checked={editForm.is_active}
                    onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                  />
                  <label htmlFor="edit-active-toggle" className="form-label" style={{ cursor: 'pointer' }}>
                    Chính sách đang hoạt động (hiệu lực)
                  </label>
                </div>
              </div>
              <div className="admin-modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setEditingPolicy(null)}>Hủy</button>
                <button type="submit" className="btn-primary" disabled={editSubmitting}>
                  {editSubmitting ? 'Đang lưu...' : 'Lưu thay đổi'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
