import { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client.js';
import { ROLE_LABELS, TEAM_ROLE_LABELS, labelOf } from '../../lib/labels.js';

export default function AdminTeamsPage() {
  const [teams, setTeams] = useState([]);
  const [selectedTeam, setSelectedTeam] = useState(null);
  const [teamDetail, setTeamDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState(null);

  // Modals
  const [showCreateTeamModal, setShowCreateTeamModal] = useState(false);
  const [createTeamForm, setCreateTeamForm] = useState({ name: '', description: '' });
  const [createTeamError, setCreateTeamError] = useState(null);
  const [createTeamSubmitting, setCreateTeamSubmitting] = useState(false);

  const [editingTeam, setEditingTeam] = useState(null);
  const [editTeamForm, setEditTeamForm] = useState({ name: '', description: '', is_active: true });
  const [editTeamError, setEditTeamError] = useState(null);
  const [editTeamSubmitting, setEditTeamSubmitting] = useState(false);

  const [showAddMemberModal, setShowAddMemberModal] = useState(false);
  const [availableUsers, setAvailableUsers] = useState([]);
  const [addMemberForm, setAddMemberForm] = useState({ user_id: '', team_role: 'MEMBER' });
  const [addMemberError, setAddMemberError] = useState(null);
  const [addMemberSubmitting, setAddMemberSubmitting] = useState(false);

  const [removingMember, setRemovingMember] = useState(null);
  const [removeSubmitting, setRemoveSubmitting] = useState(false);
  const [removeError, setRemoveError] = useState(null);

  const fetchTeams = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get('/api/teams');
      setTeams(data);
      if (data.length > 0 && !selectedTeam) {
        setSelectedTeam(data[0]);
      }
    } catch (err) {
      setError(err.message || 'Không thể tải danh sách nhóm.');
    } finally {
      setLoading(false);
    }
  }, [selectedTeam]);

  useEffect(() => {
    fetchTeams();
  }, [fetchTeams]);

  // Fetch detail for selected team
  const fetchTeamDetail = useCallback(async (teamId) => {
    if (!teamId) return;
    setDetailLoading(true);
    try {
      const data = await api.get(`/api/teams/${teamId}`);
      setTeamDetail(data);
    } catch (err) {
      setError(err.message || 'Không thể tải chi tiết nhóm.');
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedTeam) {
      fetchTeamDetail(selectedTeam.id);
    }
  }, [selectedTeam, fetchTeamDetail]);

  // Handle Create Team
  async function handleCreateTeam(e) {
    e.preventDefault();
    setCreateTeamSubmitting(true);
    setCreateTeamError(null);
    try {
      const newTeam = await api.post('/api/teams', createTeamForm);
      setShowCreateTeamModal(false);
      setCreateTeamForm({ name: '', description: '' });
      setSelectedTeam(newTeam);
      fetchTeams();
    } catch (err) {
      setCreateTeamError(err.message || 'Không thể tạo nhóm.');
    } finally {
      setCreateTeamSubmitting(false);
    }
  }

  // Handle Edit Team
  function openEditTeamModal(team) {
    setEditingTeam(team);
    setEditTeamForm({ name: team.name, description: team.description || '', is_active: team.is_active });
    setEditTeamError(null);
  }

  async function handleEditTeam(e) {
    e.preventDefault();
    setEditTeamSubmitting(true);
    setEditTeamError(null);
    try {
      const updated = await api.patch(`/api/teams/${editingTeam.id}`, editTeamForm);
      setEditingTeam(null);
      setSelectedTeam(updated);
      fetchTeams();
    } catch (err) {
      setEditTeamError(err.message || 'Không thể cập nhật nhóm.');
    } finally {
      setEditTeamSubmitting(false);
    }
  }

  // Handle Add Member
  async function openAddMember() {
    setAddMemberError(null);
    setShowAddMemberModal(true);
    try {
      const data = await api.get('/api/users?is_active=true&page_size=100');
      const existingMemberIds = new Set(
        (teamDetail?.members || []).filter((m) => m.is_active).map((m) => m.user_id)
      );
      const candidates = (data.items || []).filter((u) => !existingMemberIds.has(u.id));
      setAvailableUsers(candidates);
      if (candidates.length > 0) {
        setAddMemberForm({ user_id: candidates[0].id, team_role: 'MEMBER' });
      } else {
        setAddMemberForm({ user_id: '', team_role: 'MEMBER' });
      }
    } catch (err) {
      setAddMemberError(err.message || 'Không thể tải danh sách người dùng.');
    }
  }

  async function handleAddMember(e) {
    e.preventDefault();
    if (!addMemberForm.user_id) return;
    setAddMemberSubmitting(true);
    setAddMemberError(null);
    try {
      await api.post(`/api/teams/${selectedTeam.id}/members`, addMemberForm);
      setShowAddMemberModal(false);
      fetchTeamDetail(selectedTeam.id);
      fetchTeams();
    } catch (err) {
      setAddMemberError(err.message || 'Không thể thêm thành viên.');
    } finally {
      setAddMemberSubmitting(false);
    }
  }

  // Handle Remove Member
  async function handleRemoveMember() {
    if (!removingMember || !selectedTeam) return;
    setRemoveSubmitting(true);
    setRemoveError(null);
    try {
      await api.del(`/api/teams/${selectedTeam.id}/members/${removingMember.user_id}`);
      setRemovingMember(null);
      fetchTeamDetail(selectedTeam.id);
      fetchTeams();
    } catch (err) {
      setRemoveError(err.message || 'Không thể xóa thành viên khỏi nhóm.');
    } finally {
      setRemoveSubmitting(false);
    }
  }

  // Summary counts
  const totalTeams = teams.length;
  const activeTeams = teams.filter((t) => t.is_active).length;
  const totalAllocatedMembers = teams.reduce((acc, t) => acc + (t.member_count || 0), 0);
  const currentTeamMembers = (teamDetail?.members || []).filter((m) => m.is_active).length;

  return (
    <div className="admin-page-container">
      {/* Top KPI Summary Cards */}
      <div className="admin-summary-grid">
        <div className="admin-kpi-card">
          <div className="admin-kpi-content">
            <span className="admin-kpi-val">{totalTeams}</span>
            <span className="admin-kpi-lbl">Tổng số nhóm hỗ trợ</span>
          </div>
          <div className="admin-kpi-icon admin-kpi-icon--blue">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
              <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
            </svg>
          </div>
        </div>

        <div className="admin-kpi-card">
          <div className="admin-kpi-content">
            <span className="admin-kpi-val" style={{ color: 'var(--color-success)' }}>
              {activeTeams}
            </span>
            <span className="admin-kpi-lbl">Nhóm đang hoạt động</span>
          </div>
          <div className="admin-kpi-icon admin-kpi-icon--green">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
        </div>

        <div className="admin-kpi-card">
          <div className="admin-kpi-content">
            <span className="admin-kpi-val" style={{ color: '#7c3aed' }}>
              {totalAllocatedMembers}
            </span>
            <span className="admin-kpi-lbl">Lượt phân bổ nhân sự</span>
          </div>
          <div className="admin-kpi-icon admin-kpi-icon--purple">
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
            <span className="admin-kpi-val" style={{ color: 'var(--color-primary)' }}>
              {selectedTeam ? currentTeamMembers : 0}
            </span>
            <span className="admin-kpi-lbl">Thành viên ({selectedTeam?.name || 'Chưa chọn'})</span>
          </div>
          <div className="admin-kpi-icon admin-kpi-icon--blue">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="admin-toolbar">
        <div>
          <h2 className="admin-toolbar-title">Quản lý nhóm và phân bổ nhân sự</h2>
          <p className="admin-subtitle" style={{ margin: 0 }}>
            Tạo các nhóm hỗ trợ chuyên môn, phân công trưởng nhóm và thành viên xử lý vé
          </p>
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={() => {
            setCreateTeamError(null);
            setShowCreateTeamModal(true);
          }}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Tạo nhóm mới
        </button>
      </div>

      {error && <div className="alert-error" style={{ marginBottom: 'var(--space-3)' }}>{error}</div>}

      {loading ? (
        <div className="state-loading">Đang tải danh sách nhóm hỗ trợ…</div>
      ) : teams.length === 0 ? (
        <div className="empty-state">
          <p style={{ margin: 0 }}>Chưa có nhóm hỗ trợ nào. Nhấn "Tạo nhóm mới" để khởi tạo nhóm đầu tiên.</p>
        </div>
      ) : (
        <div className="admin-master-detail">
          {/* Left: Team List */}
          <div className="admin-master-list">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-1)', padding: '0 4px' }}>
              <span style={{ fontSize: 'var(--font-size-xs)', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Danh mục nhóm ({teams.length})
              </span>
            </div>

            {teams.map((t) => {
              const isSelected = selectedTeam?.id === t.id;
              return (
                <div
                  key={t.id}
                  className={`admin-team-card ${isSelected ? 'selected' : ''}`}
                  onClick={() => setSelectedTeam(t)}
                >
                  <div className="admin-team-card-header">
                    <strong className="admin-team-card-title">
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: isSelected ? 'var(--color-primary)' : 'var(--color-text-muted)' }}>
                        <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
                        <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
                      </svg>
                      {t.name}
                    </strong>
                    <span className={`badge ${t.is_active ? 'badge-active' : 'badge-inactive'}`}>
                      <span className={`status-dot ${t.is_active ? 'status-dot-active' : 'status-dot-inactive'}`} />
                      {t.is_active ? 'Hoạt động' : 'Tạm dừng'}
                    </span>
                  </div>

                  <p className="admin-team-card-desc">
                    {t.description || 'Chưa có mô tả nhiệm vụ cho nhóm này.'}
                  </p>

                  <div className="admin-team-card-footer">
                    <span className="badge" style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)' }}>
                      👥 {t.member_count || 0} thành viên
                    </span>
                    <button
                      type="button"
                      className="btn-secondary btn-sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        openEditTeamModal(t);
                      }}
                    >
                      Chỉnh sửa
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Right: Selected Team Detail & Members Table */}
          <div className="admin-detail-panel">
            {detailLoading ? (
              <div className="state-loading">Đang tải chi tiết thành viên nhóm…</div>
            ) : !teamDetail ? (
              <div className="empty-state">Vui lòng chọn một nhóm ở danh sách bên trái để quản lý.</div>
            ) : (
              <div>
                <div className="admin-detail-header">
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                      <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700 }}>{teamDetail.name}</h3>
                      <span className={`badge ${teamDetail.is_active ? 'badge-active' : 'badge-inactive'}`}>
                        <span className={`status-dot ${teamDetail.is_active ? 'status-dot-active' : 'status-dot-inactive'}`} />
                        {teamDetail.is_active ? 'Đang hoạt động' : 'Tạm dừng'}
                      </span>
                    </div>
                    <p style={{ margin: 'var(--space-1) 0 0', color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>
                      {teamDetail.description || 'Chưa có mô tả nhiệm vụ'}
                    </p>
                  </div>

                  <button
                    type="button"
                    className="btn-primary btn-sm"
                    onClick={openAddMember}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
                    </svg>
                    Thêm thành viên
                  </button>
                </div>

                <div style={{ marginTop: 'var(--space-4)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
                    <h4 style={{ margin: 0, fontSize: '0.9rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      Thành viên trong nhóm ({teamDetail.members?.filter((m) => m.is_active).length || 0})
                    </h4>
                  </div>

                  {teamDetail.members?.filter((m) => m.is_active).length === 0 ? (
                    <div className="empty-state" style={{ padding: 'var(--space-6)' }}>
                      <p style={{ margin: 0 }}>Nhóm này chưa có thành viên nào. Nhấn "+ Thêm thành viên" để phân bổ nhân sự.</p>
                    </div>
                  ) : (
                    <div className="table-wrap">
                      <div style={{ overflowX: 'auto' }}>
                        <table className="admin-table">
                          <thead>
                            <tr>
                              <th>THÀNH VIÊN</th>
                              <th>VAI TRÒ TRONG NHÓM</th>
                              <th>VAI TRÒ HỆ THỐNG</th>
                              <th style={{ textAlign: 'right' }}>THAO TÁC</th>
                            </tr>
                          </thead>
                          <tbody>
                            {teamDetail.members
                              .filter((m) => m.is_active)
                              .map((m) => {
                                const initial = (m.full_name || m.email || '?').charAt(0).toUpperCase();
                                return (
                                  <tr key={m.id}>
                                    <td>
                                      <div className="user-identity-cell">
                                        <span className={`user-avatar-sm user-avatar-${(m.user_role || 'agent').toLowerCase()}`}>
                                          {initial}
                                        </span>
                                        <div className="user-identity-info">
                                          <span className="user-identity-name">{m.full_name}</span>
                                          <span className="user-identity-email">{m.email}</span>
                                        </div>
                                      </div>
                                    </td>
                                    <td>
                                      <span className={`badge ${m.team_role === 'MANAGER' ? 'badge-manager' : 'badge-agent'}`}>
                                        {labelOf(TEAM_ROLE_LABELS, m.team_role)}
                                      </span>
                                    </td>
                                    <td>
                                      <span className={`badge badge-${m.user_role.toLowerCase()}`}>
                                        {labelOf(ROLE_LABELS, m.user_role)}
                                      </span>
                                    </td>
                                    <td style={{ textAlign: 'right' }}>
                                      <button
                                        type="button"
                                        className="btn-danger btn-sm"
                                        onClick={() => setRemovingMember(m)}
                                      >
                                        Xóa khỏi nhóm
                                      </button>
                                    </td>
                                  </tr>
                                );
                              })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modal: Create Team */}
      {showCreateTeamModal && (
        <div className="admin-modal-backdrop" onClick={() => setShowCreateTeamModal(false)}>
          <div className="admin-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2 className="admin-modal-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
                  <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
                </svg>
                Tạo nhóm hỗ trợ mới
              </h2>
              <button type="button" className="admin-modal-close" onClick={() => setShowCreateTeamModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateTeam}>
              <div className="admin-modal-body">
                {createTeamError && <div className="alert-error">{createTeamError}</div>}
                <div className="form-group">
                  <label className="form-label">Tên nhóm *</label>
                  <input
                    type="text"
                    required
                    className="admin-input"
                    placeholder="VD: Hỗ trợ Kỹ thuật cấp 2, Team Thanh toán…"
                    value={createTeamForm.name}
                    onChange={(e) => setCreateTeamForm({ ...createTeamForm, name: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Mô tả nhiệm vụ nhóm</label>
                  <textarea
                    className="admin-input"
                    rows={3}
                    placeholder="Mô tả phạm vi hỗ trợ và phân loại yêu cầu tiếp nhận của nhóm…"
                    value={createTeamForm.description}
                    onChange={(e) => setCreateTeamForm({ ...createTeamForm, description: e.target.value })}
                  />
                </div>
              </div>
              <div className="admin-modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setShowCreateTeamModal(false)}>Hủy bỏ</button>
                <button type="submit" className="btn-primary" disabled={createTeamSubmitting}>
                  {createTeamSubmitting ? 'Đang tạo…' : 'Xác nhận tạo nhóm'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Edit Team */}
      {editingTeam && (
        <div className="admin-modal-backdrop" onClick={() => setEditingTeam(null)}>
          <div className="admin-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2 className="admin-modal-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
                Chỉnh sửa nhóm: {editingTeam.name}
              </h2>
              <button type="button" className="admin-modal-close" onClick={() => setEditingTeam(null)}>✕</button>
            </div>
            <form onSubmit={handleEditTeam}>
              <div className="admin-modal-body">
                {editTeamError && <div className="alert-error">{editTeamError}</div>}
                <div className="form-group">
                  <label className="form-label">Tên nhóm *</label>
                  <input
                    type="text"
                    required
                    className="admin-input"
                    value={editTeamForm.name}
                    onChange={(e) => setEditTeamForm({ ...editTeamForm, name: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Mô tả nhiệm vụ</label>
                  <textarea
                    className="admin-input"
                    rows={3}
                    value={editTeamForm.description}
                    onChange={(e) => setEditTeamForm({ ...editTeamForm, description: e.target.value })}
                  />
                </div>
                <div className="form-group" style={{ flexDirection: 'row', alignItems: 'center', gap: 'var(--space-2)' }}>
                  <input
                    type="checkbox"
                    id="team-active-toggle"
                    checked={editTeamForm.is_active}
                    onChange={(e) => setEditTeamForm({ ...editTeamForm, is_active: e.target.checked })}
                  />
                  <label htmlFor="team-active-toggle" className="form-label" style={{ cursor: 'pointer' }}>
                    Nhóm đang hoạt động (cho phép tiếp nhận vé)
                  </label>
                </div>
              </div>
              <div className="admin-modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setEditingTeam(null)}>Hủy bỏ</button>
                <button type="submit" className="btn-primary" disabled={editTeamSubmitting}>
                  {editTeamSubmitting ? 'Đang lưu…' : 'Lưu thay đổi'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Add Member */}
      {showAddMemberModal && (
        <div className="admin-modal-backdrop" onClick={() => setShowAddMemberModal(false)}>
          <div className="admin-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2 className="admin-modal-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <line x1="19" y1="8" x2="19" y2="14" />
                  <line x1="22" y1="11" x2="16" y2="11" />
                </svg>
                Thêm thành viên vào {selectedTeam?.name}
              </h2>
              <button type="button" className="admin-modal-close" onClick={() => setShowAddMemberModal(false)}>✕</button>
            </div>
            <form onSubmit={handleAddMember}>
              <div className="admin-modal-body">
                {addMemberError && <div className="alert-error">{addMemberError}</div>}
                {availableUsers.length === 0 ? (
                  <div className="empty-state" style={{ padding: 'var(--space-4)' }}>
                    Tất cả tài khoản hoạt động đã có trong nhóm hoặc chưa có tài khoản khả dụng.
                  </div>
                ) : (
                  <>
                    <div className="form-group">
                      <label className="form-label">Chọn nhân viên / quản lý *</label>
                      <select
                        className="admin-select"
                        required
                        value={addMemberForm.user_id}
                        onChange={(e) => setAddMemberForm({ ...addMemberForm, user_id: e.target.value })}
                      >
                        {availableUsers.map((u) => (
                          <option key={u.id} value={u.id}>
                            {u.full_name} ({u.email}) — {labelOf(ROLE_LABELS, u.role)}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Vai trò trong nhóm *</label>
                      <select
                        className="admin-select"
                        value={addMemberForm.team_role}
                        onChange={(e) => setAddMemberForm({ ...addMemberForm, team_role: e.target.value })}
                      >
                        <option value="MEMBER">Thành viên (Tiếp nhận và giải quyết vé hỗ trợ)</option>
                        <option value="MANAGER">Trưởng nhóm (Phân công và điều phối nội bộ nhóm)</option>
                      </select>
                    </div>
                  </>
                )}
              </div>
              <div className="admin-modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setShowAddMemberModal(false)}>Hủy bỏ</button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={addMemberSubmitting || availableUsers.length === 0}
                >
                  {addMemberSubmitting ? 'Đang thêm…' : 'Thêm vào nhóm'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Confirmation Dialog: Remove Member */}
      {removingMember && (
        <div className="admin-modal-backdrop" onClick={() => setRemovingMember(null)}>
          <div className="admin-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2 className="admin-modal-title">Xác nhận xóa thành viên</h2>
              <button type="button" className="admin-modal-close" onClick={() => setRemovingMember(null)}>✕</button>
            </div>
            <div className="admin-modal-body">
              {removeError && <div className="alert-error">{removeError}</div>}
              <p style={{ margin: 0, lineHeight: 1.5 }}>
                Bạn có chắc chắn muốn xóa thành viên <strong>{removingMember.full_name}</strong> khỏi nhóm{' '}
                <strong>{selectedTeam?.name}</strong>?
              </p>
              <div className="alert-warning" style={{ marginTop: 'var(--space-2)', fontSize: 'var(--font-size-xs)' }}>
                ℹ️ Lưu ý: Lịch sử xử lý vé trước đây của thành viên này trong hệ thống vẫn được bảo lưu vĩnh viễn trong nhật ký kiểm toán.
              </div>
            </div>
            <div className="admin-modal-footer">
              <button type="button" className="btn-secondary" onClick={() => setRemovingMember(null)}>Hủy bỏ</button>
              <button
                type="button"
                className="btn-danger"
                disabled={removeSubmitting}
                onClick={handleRemoveMember}
              >
                {removeSubmitting ? 'Đang xóa…' : 'Xác nhận xóa khỏi nhóm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
