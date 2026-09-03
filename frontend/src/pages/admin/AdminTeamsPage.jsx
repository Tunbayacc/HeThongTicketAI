import { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client.js';

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
      // Fetch only active users
      const data = await api.get('/api/users?is_active=true&page_size=100');
      // Filter out users who are already active members of this team
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

  return (
    <div>
      <div className="admin-toolbar">
        <div>
          <h2 style={{ margin: 0, fontSize: '1.2rem' }}>Quản lý nhóm và phân bổ nhân sự</h2>
          <p className="admin-subtitle">Tạo nhóm hỗ trợ chuyên trách và chỉ định thành viên, quản lý nhóm</p>
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={() => {
            setCreateTeamError(null);
            setShowCreateTeamModal(true);
          }}
        >
          + Tạo nhóm mới
        </button>
      </div>

      {error && <div className="alert-error" style={{ marginBottom: 'var(--space-3)' }}>{error}</div>}

      {loading ? (
        <div className="state-loading">Đang tải danh sách nhóm...</div>
      ) : teams.length === 0 ? (
        <div className="state-empty">Chưa có nhóm hỗ trợ nào. Bấm "Tạo nhóm mới" để bắt đầu.</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, 320px) 1fr', gap: 'var(--space-4)', alignItems: 'start' }}>
          {/* Left Column: Team List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-muted)' }}>
              Danh sách nhóm ({teams.length})
            </span>
            {teams.map((t) => (
              <div
                key={t.id}
                className="admin-card"
                style={{
                  cursor: 'pointer',
                  borderColor: selectedTeam?.id === t.id ? 'var(--color-primary)' : 'var(--color-border)',
                  backgroundColor: selectedTeam?.id === t.id ? 'var(--color-surface)' : 'var(--color-bg)',
                  boxShadow: selectedTeam?.id === t.id ? '0 0 0 1px var(--color-primary)' : 'var(--shadow-sm)',
                }}
                onClick={() => setSelectedTeam(t)}
              >
                <div className="admin-card-header">
                  <strong className="admin-card-title">{t.name}</strong>
                  <span className={`badge ${t.is_active ? 'badge-active' : 'badge-inactive'}`}>
                    {t.is_active ? 'Hoạt động' : 'Tạm dừng'}
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--color-text-muted)', lineHeight: 1.4 }}>
                  {t.description || 'Chưa có mô tả'}
                </p>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'var(--space-1)', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                  <span>{t.member_count} thành viên</span>
                  <button
                    type="button"
                    className="btn-secondary btn-sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      openEditTeamModal(t);
                    }}
                  >
                    Sửa
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Right Column: Selected Team Detail & Members */}
          <div style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', background: 'var(--color-bg)', padding: 'var(--space-4)' }}>
            {detailLoading ? (
              <div className="state-loading">Đang tải thành viên nhóm...</div>
            ) : !teamDetail ? (
              <div className="state-empty">Chọn một nhóm bên trái để xem thành viên.</div>
            ) : (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-2)', borderBottom: '1px solid var(--color-border)', paddingBottom: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.25rem' }}>{teamDetail.name}</h3>
                    <p style={{ margin: 'var(--space-1) 0 0', color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>
                      {teamDetail.description || 'Không có mô tả'}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="btn-primary btn-sm"
                    onClick={openAddMember}
                  >
                    + Thêm thành viên
                  </button>
                </div>

                <h4 style={{ margin: '0 0 var(--space-2)', fontSize: '0.95rem' }}>
                  Thành viên nhóm ({teamDetail.members?.filter((m) => m.is_active).length || 0})
                </h4>

                {teamDetail.members?.filter((m) => m.is_active).length === 0 ? (
                  <div className="state-empty" style={{ padding: 'var(--space-4)' }}>
                    Nhóm này chưa có thành viên hoạt động nào.
                  </div>
                ) : (
                  <div className="admin-table-container">
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>Thành viên</th>
                          <th>Email</th>
                          <th>Vai trò trong nhóm</th>
                          <th>Vai trò hệ thống</th>
                          <th style={{ textAlign: 'right' }}>Thao tác</th>
                        </tr>
                      </thead>
                      <tbody>
                        {teamDetail.members
                          .filter((m) => m.is_active)
                          .map((m) => (
                            <tr key={m.id}>
                              <td style={{ fontWeight: 600 }}>{m.full_name}</td>
                              <td>{m.email}</td>
                              <td>
                                <span className={`badge ${m.team_role === 'MANAGER' ? 'badge-manager' : 'badge-agent'}`}>
                                  {m.team_role === 'MANAGER' ? 'Quản lý nhóm (Manager)' : 'Thành viên (Member)'}
                                </span>
                              </td>
                              <td>
                                <span className={`badge badge-${m.user_role.toLowerCase()}`}>
                                  {m.user_role}
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
                          ))}
                      </tbody>
                    </table>
                  </div>
                )}
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
              <h2 className="admin-modal-title">Tạo nhóm hỗ trợ mới</h2>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setShowCreateTeamModal(false)}>✕</button>
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
                    placeholder="VD: Team Kỹ thuật, Team Thanh toán..."
                    value={createTeamForm.name}
                    onChange={(e) => setCreateTeamForm({ ...createTeamForm, name: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Mô tả nhiệm vụ</label>
                  <textarea
                    className="admin-input"
                    rows={3}
                    placeholder="Mô tả phạm vi xử lý vé của nhóm..."
                    value={createTeamForm.description}
                    onChange={(e) => setCreateTeamForm({ ...createTeamForm, description: e.target.value })}
                  />
                </div>
              </div>
              <div className="admin-modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setShowCreateTeamModal(false)}>Hủy</button>
                <button type="submit" className="btn-primary" disabled={createTeamSubmitting}>
                  {createTeamSubmitting ? 'Đang tạo...' : 'Tạo nhóm'}
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
              <h2 className="admin-modal-title">Chỉnh sửa nhóm: {editingTeam.name}</h2>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setEditingTeam(null)}>✕</button>
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
                  <label className="form-label">Mô tả</label>
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
                    Nhóm đang hoạt động
                  </label>
                </div>
              </div>
              <div className="admin-modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setEditingTeam(null)}>Hủy</button>
                <button type="submit" className="btn-primary" disabled={editTeamSubmitting}>
                  {editTeamSubmitting ? 'Đang lưu...' : 'Lưu thay đổi'}
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
              <h2 className="admin-modal-title">Thêm thành viên vào {selectedTeam?.name}</h2>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setShowAddMemberModal(false)}>✕</button>
            </div>
            <form onSubmit={handleAddMember}>
              <div className="admin-modal-body">
                {addMemberError && <div className="alert-error">{addMemberError}</div>}
                {availableUsers.length === 0 ? (
                  <p className="state-empty" style={{ padding: 'var(--space-3)' }}>
                    Không có người dùng hoạt động nào khả dụng để thêm.
                  </p>
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
                            {u.full_name} ({u.email}) — {u.role}
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
                        <option value="MEMBER">Thành viên (Member - xử lý vé)</option>
                        <option value="MANAGER">Quản lý nhóm (Manager - phân công vé)</option>
                      </select>
                    </div>
                  </>
                )}
              </div>
              <div className="admin-modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setShowAddMemberModal(false)}>Hủy</button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={addMemberSubmitting || availableUsers.length === 0}
                >
                  {addMemberSubmitting ? 'Đang thêm...' : 'Thêm vào nhóm'}
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
              <button type="button" className="btn-secondary btn-sm" onClick={() => setRemovingMember(null)}>✕</button>
            </div>
            <div className="admin-modal-body">
              {removeError && <div className="alert-error">{removeError}</div>}
              <p>
                Bạn có chắc chắn muốn xóa <strong>{removingMember.full_name}</strong> khỏi nhóm{' '}
                <strong>{selectedTeam?.name}</strong>?
              </p>
              <p className="form-hint">
                Lịch sử xử lý vé trước đây của thành viên này vẫn sẽ được giữ nguyên toàn vẹn trong nhật ký.
              </p>
            </div>
            <div className="admin-modal-footer">
              <button type="button" className="btn-secondary" onClick={() => setRemovingMember(null)}>Hủy</button>
              <button
                type="button"
                className="btn-danger"
                disabled={removeSubmitting}
                onClick={handleRemoveMember}
              >
                {removeSubmitting ? 'Đang xóa...' : 'Xóa khỏi nhóm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
