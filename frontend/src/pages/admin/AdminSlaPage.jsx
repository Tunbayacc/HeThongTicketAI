import { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client.js';

const PRIORITIES = [
  { value: 'URGENT', label: 'Khẩn cấp (URGENT)', color: '#dc2626', bg: '#fef2f2', border: '#fecaca' },
  { value: 'HIGH', label: 'Mức cao (HIGH)', color: '#ea580c', bg: '#fff7ed', border: '#fed7aa' },
  { value: 'MEDIUM', label: 'Trung bình (MEDIUM)', color: '#d97706', bg: '#fffbeb', border: '#fde68a' },
  { value: 'LOW', label: 'Mức thấp (LOW)', color: '#2563eb', bg: '#eff6ff', border: '#bfdbfe' },
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

  // Summary counts
  const activeCount = policies.filter((p) => p.is_active).length;
  const urgentCount = policies.filter((p) => p.priority === 'URGENT' && p.is_active).length;
  const highCount = policies.filter((p) => p.priority === 'HIGH' && p.is_active).length;
  const pauseCount = policies.filter((p) => p.pause_on_pending && p.is_active).length;

  return (
    <div className="admin-page-container">
      {/* Top KPI Summary Cards */}
      <div className="admin-summary-grid">
        <div className="admin-kpi-card">
          <div className="admin-kpi-content">
            <span className="admin-kpi-val" style={{ color: 'var(--color-success)' }}>
              {activeCount}
            </span>
            <span className="admin-kpi-lbl">Chính sách đang hiệu lực</span>
          </div>
          <div className="admin-kpi-icon admin-kpi-icon--green">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
        </div>

        <div className="admin-kpi-card">
          <div className="admin-kpi-content">
            <span className="admin-kpi-val" style={{ color: '#dc2626' }}>
              {urgentCount}
            </span>
            <span className="admin-kpi-lbl">Tier Khẩn cấp (URGENT)</span>
          </div>
          <div className="admin-kpi-icon admin-kpi-icon--red">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
        </div>

        <div className="admin-kpi-card">
          <div className="admin-kpi-content">
            <span className="admin-kpi-val" style={{ color: '#ea580c' }}>
              {highCount}
            </span>
            <span className="admin-kpi-lbl">Tier Ưu tiên cao (HIGH)</span>
          </div>
          <div className="admin-kpi-icon admin-kpi-icon--amber">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="18 15 12 9 6 15" />
            </svg>
          </div>
        </div>

        <div className="admin-kpi-card">
          <div className="admin-kpi-content">
            <span className="admin-kpi-val" style={{ color: 'var(--color-primary)' }}>
              {pauseCount}
            </span>
            <span className="admin-kpi-lbl">Tạm dừng khi chờ (Pending)</span>
          </div>
          <div className="admin-kpi-icon admin-kpi-icon--blue">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="10" y1="15" x2="10" y2="9" />
              <line x1="14" y1="15" x2="14" y2="9" />
            </svg>
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="admin-toolbar">
        <div>
          <h2 className="admin-toolbar-title">Chính sách cam kết dịch vụ (SLA)</h2>
          <p className="admin-subtitle" style={{ margin: 0 }}>
            Quy định thời hạn phản hồi đầu tiên và thời hạn giải quyết vé theo từng mức độ ưu tiên
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
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Thêm chính sách SLA
        </button>
      </div>

      {error && <div className="alert-error" style={{ marginBottom: 'var(--space-3)' }}>{error}</div>}

      {loading ? (
        <div className="state-loading">Đang tải danh sách chính sách SLA…</div>
      ) : policies.length === 0 ? (
        <div className="empty-state">
          <p style={{ margin: 0 }}>Chưa có chính sách SLA nào trong hệ thống. Nhấn "Thêm chính sách SLA" để bắt đầu.</p>
        </div>
      ) : (
        <div>
          {PRIORITIES.map((pGroup) => {
            const groupPolicies = policies.filter((p) => p.priority === pGroup.value);
            return (
              <div key={pGroup.value} className="sla-tier-group">
                <div className="sla-tier-header">
                  <h3 className="sla-tier-title">
                    <span
                      style={{
                        display: 'inline-block',
                        width: 10,
                        height: 10,
                        borderRadius: '50%',
                        backgroundColor: pGroup.color,
                        boxShadow: `0 0 0 2px ${pGroup.border}`,
                      }}
                    />
                    {pGroup.label}
                  </h3>
                  <span className="sla-tier-badge" style={{ background: pGroup.bg, color: pGroup.color, border: `1px solid ${pGroup.border}` }}>
                    {groupPolicies.length} chính sách
                  </span>
                </div>

                {groupPolicies.length === 0 ? (
                  <div className="empty-state" style={{ padding: 'var(--space-4)', textAlign: 'left', fontStyle: 'italic' }}>
                    Chưa có chính sách SLA nào cho mức {pGroup.label.toLowerCase()}.
                  </div>
                ) : (
                  <div className="admin-card-grid">
                    {groupPolicies.map((p) => (
                      <div
                        key={p.id}
                        className="sla-policy-card"
                        style={{
                          borderLeft: `4px solid ${p.is_active ? pGroup.color : 'var(--color-border)'}`,
                          opacity: p.is_active ? 1 : 0.8,
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--space-2)' }}>
                          <strong style={{ fontSize: 'var(--font-size-base)', color: 'var(--color-text)', lineHeight: 1.3 }}>
                            {p.name}
                          </strong>
                          <span className={`badge ${p.is_active ? 'badge-active' : 'badge-inactive'}`}>
                            <span className={`status-dot ${p.is_active ? 'status-dot-active' : 'status-dot-inactive'}`} />
                            {p.is_active ? 'Hiệu lực' : 'Hết hạn'}
                          </span>
                        </div>

                        {/* Metric duration chips */}
                        <div className="sla-metric-pill-row">
                          <div className="sla-metric-cell">
                            <span className="sla-metric-label">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="12" cy="12" r="10" />
                                <polyline points="12 6 12 12 16 14" />
                              </svg>
                              Phản hồi đầu
                            </span>
                            <span className="sla-metric-value">{formatMinutes(p.first_response_minutes)}</span>
                          </div>
                          <div className="sla-metric-cell">
                            <span className="sla-metric-label">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                                <polyline points="22 4 12 14.01 9 11.01" />
                              </svg>
                              Giải quyết xong
                            </span>
                            <span className="sla-metric-value">{formatMinutes(p.resolution_minutes)}</span>
                          </div>
                        </div>

                        {/* Conditions & timeline tags */}
                        <div className="sla-meta-tags">
                          <span className="sla-meta-tag">
                            ⏸️ Pending:{' '}
                            <strong style={{ color: p.pause_on_pending ? 'var(--color-primary)' : 'var(--color-text-muted)', marginLeft: 3 }}>
                              {p.pause_on_pending ? 'Tạm dừng tính hạn' : 'Tiếp tục tính hạn'}
                            </strong>
                          </span>
                          <span className="sla-meta-tag">
                            📅 Từ {new Date(p.effective_from).toLocaleDateString('vi-VN')}
                            {p.effective_to ? ` đến ${new Date(p.effective_to).toLocaleDateString('vi-VN')}` : ' (vô thời hạn)'}
                          </span>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'auto', paddingTop: 'var(--space-2)' }}>
                          <button
                            type="button"
                            className="btn-secondary btn-sm"
                            onClick={() => openEditModal(p)}
                          >
                            Chỉnh sửa SLA
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
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
              <h2 className="admin-modal-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
                Tạo chính sách SLA mới
              </h2>
              <button type="button" className="admin-modal-close" onClick={() => setShowCreateModal(false)}>✕</button>
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
                    placeholder="VD: SLA Khẩn cấp Q4/2026, SLA Doanh nghiệp VIP…"
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
                    <option value="URGENT">Khẩn cấp (URGENT) — Vé sự cố nghiêm trọng, ảnh hưởng toàn hệ thống</option>
                    <option value="HIGH">Mức cao (HIGH) — Gián đoạn dịch vụ quan trọng của khách hàng</option>
                    <option value="MEDIUM">Trung bình (MEDIUM) — Yêu cầu nghiệp vụ và cấu hình thông thường</option>
                    <option value="LOW">Mức thấp (LOW) — Câu hỏi hỗ trợ, góp ý và yêu cầu phi khẩn cấp</option>
                  </select>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                  <div className="form-group">
                    <label className="form-label">Hạn phản hồi (phút) *</label>
                    <input
                      type="number"
                      required
                      min={1}
                      className="admin-input"
                      value={createForm.first_response_minutes}
                      onChange={(e) => setCreateForm({ ...createForm, first_response_minutes: e.target.value })}
                    />
                    <span className="form-hint">⏱️ {formatMinutes(Number(createForm.first_response_minutes))}</span>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Hạn giải quyết (phút) *</label>
                    <input
                      type="number"
                      required
                      min={1}
                      className="admin-input"
                      value={createForm.resolution_minutes}
                      onChange={(e) => setCreateForm({ ...createForm, resolution_minutes: e.target.value })}
                    />
                    <span className="form-hint">⏱️ {formatMinutes(Number(createForm.resolution_minutes))}</span>
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
                    Tạm dừng tính hạn SLA khi vé ở trạng thái Chờ (Pending)
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
                    <label className="form-label">Hiệu lực đến (để trống: vô hạn)</label>
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
                    Kích hoạt hiệu lực chính sách ngay
                  </label>
                </div>
              </div>
              <div className="admin-modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setShowCreateModal(false)}>Hủy bỏ</button>
                <button type="submit" className="btn-primary" disabled={createSubmitting}>
                  {createSubmitting ? 'Đang tạo…' : 'Xác nhận tạo SLA'}
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
              <h2 className="admin-modal-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
                Chỉnh sửa: {editingPolicy.name}
              </h2>
              <button type="button" className="admin-modal-close" onClick={() => setEditingPolicy(null)}>✕</button>
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
                    <label className="form-label">Hạn phản hồi (phút) *</label>
                    <input
                      type="number"
                      required
                      min={1}
                      className="admin-input"
                      value={editForm.first_response_minutes}
                      onChange={(e) => setEditForm({ ...editForm, first_response_minutes: e.target.value })}
                    />
                    <span className="form-hint">⏱️ {formatMinutes(Number(editForm.first_response_minutes))}</span>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Hạn giải quyết (phút) *</label>
                    <input
                      type="number"
                      required
                      min={1}
                      className="admin-input"
                      value={editForm.resolution_minutes}
                      onChange={(e) => setEditForm({ ...editForm, resolution_minutes: e.target.value })}
                    />
                    <span className="form-hint">⏱️ {formatMinutes(Number(editForm.resolution_minutes))}</span>
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
                    Tạm dừng tính hạn SLA khi vé ở trạng thái Chờ (Pending)
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
                    <label className="form-label">Hiệu lực đến (để trống: vô hạn)</label>
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
                <button type="button" className="btn-secondary" onClick={() => setEditingPolicy(null)}>Hủy bỏ</button>
                <button type="submit" className="btn-primary" disabled={editSubmitting}>
                  {editSubmitting ? 'Đang lưu…' : 'Lưu thay đổi'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
