import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, triggerDownload } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import {
  CATEGORY_LABELS, PRIORITY_LABELS, STATUS_LABELS, VISIBILITY_LABELS,
  fmtDateTime, labelOf,
} from '../lib/labels.js';
import '../styles/tickets.css';

const MAX_FILES = 5;

// Mirror of backend state_machine.STATUS_FLOW (Task 1) — the UI only offers legal moves.
const NEXT_STATUSES = {
  OPEN: ['IN_PROGRESS', 'PENDING'],
  IN_PROGRESS: ['PENDING', 'RESOLVED'],
  PENDING: ['IN_PROGRESS'],
  RESOLVED: ['CLOSED', 'IN_PROGRESS'],
  CLOSED: ['IN_PROGRESS'],
};

function fmtBytes(n) {
  if (n == null) return '—';
  if (n < 1024) return `${n} B`;
  return `${(n / 1024).toFixed(1)} KB`;
}

function eventText(h) {
  // changed_by is a user id (HistoryOut has no author_name); the audit log holds
  // the actor for S6 — the timeline shows the event + reason, not a raw id.
  switch (h.event_type) {
    case 'STATUS_CHANGED':
      return `Trạng thái: ${h.old_value || '—'} → ${h.new_value || '—'}`;
    case 'ASSIGNED':
      return 'Phân công được cập nhật';
    case 'COMMENT_ADDED':
      return 'Bình luận được thêm';
    case 'ATTACHMENT_ADDED':
      return 'Tệp đính kèm được thêm';
    case 'FIELD_UPDATED':
      return `Cập nhật ${h.field_name || 'trường'}: ${String(h.old_value ?? '—')} → ${String(h.new_value ?? '—')}`;
    default:
      return `${h.event_type}${h.field_name ? ` (${h.field_name})` : ''}`;
  }
}

export default function TicketDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const canAssign = user?.role === 'MANAGER' || user?.role === 'ADMIN';

  const [detail, setDetail] = useState(null); // TicketDetail | null
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [actionError, setActionError] = useState(null);

  // status dialog
  const [statusDialog, setStatusDialog] = useState(null); // target status | null
  const [statusReason, setStatusReason] = useState('');
  const [statusBusy, setStatusBusy] = useState(false);

  // edit dialog
  const [editOpen, setEditOpen] = useState(false);
  const [editReason, setEditReason] = useState('');
  const [editForm, setEditForm] = useState({ subject: '', description: '', category: '', priority: '' });
  const [editBusy, setEditBusy] = useState(false);

  // assign dialog
  const [assignOpen, setAssignOpen] = useState(false);
  const [teams, setTeams] = useState([]);
  const [teamId, setTeamId] = useState('');
  const [assigneeId, setAssigneeId] = useState('');
  const [assignReason, setAssignReason] = useState('');
  const [assignBusy, setAssignBusy] = useState(false);

  // comment composer
  const [content, setContent] = useState('');
  const [visibility, setVisibility] = useState('PUBLIC');
  const [files, setFiles] = useState([]);
  const [commentBusy, setCommentBusy] = useState(false);

  async function loadDetail() {
    setLoading(true);
    setLoadError(null);
    try {
      const body = await api.get(`/api/tickets/${id}`);
      setDetail(body);
      setEditForm({
        subject: body.subject, description: body.description,
        category: body.category, priority: body.priority,
      });
      setTeamId(body.team_id || '');
      setAssigneeId(body.assigned_to || '');
    } catch (err) {
      setLoadError(err.message || 'Không thể tải vé.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDetail();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // ---- status change -------------------------------------------------------
  const submitStatus = useCallback(async () => {
    const reopen = (detail?.status === 'RESOLVED' || detail?.status === 'CLOSED') && statusDialog === 'IN_PROGRESS';
    if (reopen && !statusReason.trim()) {
      setActionError('Cần nhập lý do khi mở lại vé.');
      return;
    }
    setStatusBusy(true);
    setActionError(null);
    try {
      const body = await api.post(`/api/tickets/${id}/status`, {
        status: statusDialog,
        reason: statusReason.trim() || null,
        version: detail.version,
      });
      setDetail(body);
      setEditForm({ subject: body.subject, description: body.description, category: body.category, priority: body.priority });
      setStatusDialog(null);
      setStatusReason('');
    } catch (err) {
      handleActionError(err);
    } finally {
      setStatusBusy(false);
    }
  }, [detail, statusDialog, statusReason, id]);

  // ---- edit fields ----------------------------------------------------------
  const submitEdit = useCallback(async () => {
    setEditBusy(true);
    setActionError(null);
    try {
      const patch = { version: detail.version };
      for (const key of ['subject', 'description', 'category', 'priority']) {
        if (editForm[key] !== detail[key]) patch[key] = editForm[key];
      }
      if (editReason.trim()) patch.reason = editReason.trim();
      const body = await api.patch(`/api/tickets/${id}`, patch);
      setDetail(body);
      setEditOpen(false);
      setEditReason('');
      setEditForm({
        subject: body.subject, description: body.description,
        category: body.category, priority: body.priority,
      });
    } catch (err) {
      handleActionError(err);
    } finally {
      setEditBusy(false);
    }
  }, [detail, editForm, editReason, id]);

  // ---- assign ---------------------------------------------------------------
  const openAssign = useCallback(async () => {
    setActionError(null);
    if (teams.length === 0) {
      try {
        const body = await api.get('/api/teams');
        setTeams(body);
        const preferred = body.find((t) => String(t.id) === String(teamId)) || body[0];
        if (preferred) {
          setTeamId(String(preferred.id));
          setAssigneeId(detail?.assigned_to && preferred.members.some((m) => String(m.id) === String(detail.assigned_to))
            ? detail.assigned_to : '');
        }
      } catch (err) {
        setActionError(err.message || 'Không thể tải danh sách nhóm.');
        return;
      }
    }
    setAssignOpen(true);
  }, [teams, teamId, detail]);

  const submitAssign = useCallback(async () => {
    if (!teamId) { setActionError('Vui lòng chọn nhóm.'); return; }
    setAssignBusy(true);
    setActionError(null);
    try {
      const body = await api.post(`/api/tickets/${id}/assign`, {
        team_id: teamId,
        assigned_to: assigneeId || null,
        reason: assignReason.trim() || null,
        version: detail.version,
      });
      setDetail(body);
      setAssignOpen(false);
      setAssignReason('');
    } catch (err) {
      handleActionError(err);
    } finally {
      setAssignBusy(false);
    }
  }, [detail, teamId, assigneeId, assignReason, id]);

  // ---- comment --------------------------------------------------------------
  const submitComment = useCallback(async () => {
    if (!content.trim()) { setActionError('Vui lòng nhập nội dung bình luận.'); return; }
    if (files.length > MAX_FILES) { setActionError(`Mỗi bình luận tối đa ${MAX_FILES} tệp.`); return; }
    setCommentBusy(true);
    setActionError(null);
    try {
      const fd = new FormData();
      fd.append('content', content.trim());
      fd.append('visibility', visibility);
      files.forEach((f) => fd.append('files', f));
      const body = await api.postForm(`/api/tickets/${id}/comments`, fd);
      setDetail(body);
      setContent('');
      setFiles([]);
      setVisibility('PUBLIC');
    } catch (err) {
      handleActionError(err);
    } finally {
      setCommentBusy(false);
    }
  }, [id, content, visibility, files]);

  function handleActionError(err) {
    if (err.error_code === 'VERSION_CONFLICT' || err.status === 409) {
      setActionError('Vé đã được người khác cập nhật. Đã tải lại dữ liệu mới nhất — vui lòng thử lại.');
      loadDetail();
    } else if (err.status === 403) {
      setActionError('Bạn không có quyền thực hiện thao tác này.');
    } else if (err.error_code === 'INVALID_STATUS_TRANSITION') {
      setActionError('Không thể chuyển sang trạng thái này.');
    } else if (err.error_code === 'ASSIGNEE_NOT_IN_TEAM') {
      setActionError('Người được phân công không thuộc nhóm đã chọn.');
    } else {
      setActionError(err.message || 'Thao tác thất bại. Vui lòng thử lại.');
    }
  }

  async function download(att) {
    try {
      const blob = await api.fetchBlob(`/api/attachments/${att.id}/download`);
      triggerDownload(blob, att.original_name);
    } catch (err) {
      setActionError(err.message || 'Không thể tải tệp.');
    }
  }

  if (loading) return <section className="page"><p className="text-muted">Đang tải…</p></section>;
  if (loadError) {
    return (
      <section className="page">
        <p className="form-error" role="alert">{loadError}</p>
        <button className="btn-secondary" onClick={() => navigate('/app/tickets')}>← Quay lại danh sách</button>
      </section>
    );
  }

  const currentTeam = teams.find((t) => String(t.id) === String(teamId));

  return (
    <section className="page ticket-detail">
      <p className="back-link"><Link to="/app/tickets">← Danh sách vé</Link></p>

      <header className="ticket-head">
        <div className="ticket-title-row">
          <h1>{detail.subject}</h1>
          <span className="code-cell code-badge">{detail.ticket_code}</span>
        </div>
        <div className="badge-row">
          <span className={`badge badge--${(detail.status || '').toLowerCase()}`}>{labelOf(STATUS_LABELS, detail.status)}</span>
          <span className={`badge badge--${(detail.priority || '').toLowerCase()}`}>{labelOf(PRIORITY_LABELS, detail.priority)}</span>
          <span className="badge">{labelOf(CATEGORY_LABELS, detail.category)}</span>
        </div>
        <p className="text-muted">
          {detail.requester_name} · {detail.requester_email} · Gửi lúc {fmtDateTime(detail.created_at)}
        </p>
        <p className="text-muted">
          Nhóm: {detail.team_name || '—'} · Người phụ trách: {detail.assignee_name || 'Chưa phân công'}
        </p>
        {detail.needs_reassignment && (
          <p className="form-error needs-reassign" role="alert">
            Vé này cần được phân công lại — người phụ trách hiện tại đã bị vô hiệu hóa.
            {canAssign && (
              <button className="btn-secondary" type="button" onClick={openAssign}>Phân công lại</button>
            )}
          </p>
        )}
        {detail.resolution_due_at && (
          <p className="text-muted">Hạn xử lý: {fmtDateTime(detail.resolution_due_at)}</p>
        )}
      </header>

      {actionError && <p className="form-error" role="alert">{actionError}</p>}

      <div className="ticket-actions">
        <button className="btn-secondary" onClick={() => { setActionError(null); setEditOpen(true); }}>Chỉnh sửa</button>
        {canAssign && <button className="btn-secondary" onClick={openAssign}>Phân công</button>}
      </div>

      <div className="ticket-actions">
        <span className="text-muted">Đổi trạng thái:</span>
        {(NEXT_STATUSES[detail.status] || []).map((target) => (
          <button key={target} className="btn-secondary" type="button"
            onClick={() => { setActionError(null); setStatusReason(''); setStatusDialog(target); }}>
            {labelOf(STATUS_LABELS, target)}
          </button>
        ))}
      </div>

      <section className="ticket-description">
        <h2>Mô tả</h2>
        <p className="pre-wrap">{detail.description}</p>
      </section>

      <section className="composer">
        <h2>Phản hồi</h2>
        <label className="field">
          <span>Loại phản hồi</span>
          <select value={visibility} onChange={(e) => setVisibility(e.target.value)}>
            <option value="PUBLIC">Công khai (khách hàng xem được khi tra cứu)</option>
            <option value="INTERNAL">Nội bộ (chỉ nhân viên)</option>
          </select>
        </label>
        <textarea rows={4} value={content} onChange={(e) => setContent(e.target.value)} placeholder="Nhập nội dung phản hồi…" />
        <label className="field">
          <span>Tệp đính kèm (tối đa {MAX_FILES})</span>
          <input type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.txt,.docx"
            onChange={(e) => setFiles([...e.target.files])} />
        </label>
        <button className="btn-primary" disabled={commentBusy} onClick={submitComment}>
          {commentBusy ? 'Đang gửi…' : 'Gửi phản hồi'}
        </button>
      </section>

      <section className="timeline">
        <h2>Hoạt động</h2>
        <ul className="timeline-list">
          {detail.history.map((h) => (
            <li key={`h-${h.id}`} className="timeline-item timeline-event">
              <span className="event-text">{eventText(h)}</span>
              <span className="text-muted">{fmtDateTime(h.created_at)}</span>
              {h.reason && <p className="text-muted">Lý do: {h.reason}</p>}
            </li>
          ))}
          {detail.comments.map((c) => (
            <li key={`c-${c.id}`} className="timeline-item timeline-comment">
              <div className="comment-meta">
                <strong>{c.author_name || '—'}</strong>
                <span className={`badge badge--${(c.visibility || '').toLowerCase()}`}>{labelOf(VISIBILITY_LABELS, c.visibility)}</span>
                <span className="text-muted">{fmtDateTime(c.created_at)}</span>
              </div>
              <p className="pre-wrap">{c.content}</p>
            </li>
          ))}
          {detail.attachments.filter((a) => !a.comment).map((a) => (
            <li key={`a-${a.id}`} className="timeline-item timeline-attachment">
              <button className="linklike" onClick={() => download(a)}>📎 {a.original_name}</button>
              <span className="text-muted">{fmtBytes(a.size_bytes)}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* Status change dialog */}
      {statusDialog && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Đổi trạng thái">
          <div className="modal">
            <h2>Đổi trạng thái thành {labelOf(STATUS_LABELS, statusDialog)}?</h2>
            <p className="text-muted">Mã {detail.ticket_code} — trạng thái hiện tại: {labelOf(STATUS_LABELS, detail.status)}</p>
            <label className="field">
              <span>Lý do {(detail.status === 'RESOLVED' || detail.status === 'CLOSED') && statusDialog === 'IN_PROGRESS' ? '(bắt buộc khi mở lại)' : '(không bắt buộc)'}</span>
              <textarea rows={3} value={statusReason} onChange={(e) => setStatusReason(e.target.value)} />
            </label>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setStatusDialog(null)} disabled={statusBusy}>Hủy</button>
              <button className="btn-primary" onClick={submitStatus} disabled={statusBusy}>
                {statusBusy ? 'Đang lưu…' : 'Xác nhận đổi trạng thái'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit dialog */}
      {editOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Chỉnh sửa vé">
          <div className="modal">
            <h2>Chỉnh sửa vé</h2>
            <label className="field"><span>Tiêu đề</span>
              <input value={editForm.subject} maxLength={200}
                onChange={(e) => setEditForm((f) => ({ ...f, subject: e.target.value }))} />
            </label>
            <label className="field"><span>Mô tả</span>
              <textarea rows={4} value={editForm.description} maxLength={20000}
                onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))} />
            </label>
            <label className="field"><span>Phân loại</span>
              <select value={editForm.category}
                onChange={(e) => setEditForm((f) => ({ ...f, category: e.target.value }))}>
                {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            <label className="field"><span>Ưu tiên</span>
              <select value={editForm.priority}
                onChange={(e) => setEditForm((f) => ({ ...f, priority: e.target.value }))}>
                {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            <label className="field"><span>Lý do thay đổi</span>
              <input value={editReason} maxLength={500} onChange={(e) => setEditReason(e.target.value)} />
            </label>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setEditOpen(false)} disabled={editBusy}>Hủy</button>
              <button className="btn-primary" onClick={submitEdit} disabled={editBusy}>
                {editBusy ? 'Đang lưu…' : 'Lưu thay đổi'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Assign dialog */}
      {assignOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Phân công vé">
          <div className="modal">
            <h2>Phân công vé</h2>
            <label className="field"><span>Nhóm xử lý</span>
              <select value={teamId} onChange={(e) => { setTeamId(e.target.value); setAssigneeId(''); }}>
                <option value="">— Chọn nhóm —</option>
                {teams.map((t) => <option key={t.id} value={String(t.id)}>{t.name}</option>)}
              </select>
            </label>
            <label className="field"><span>Người phụ trách (để trống nếu chỉ gán nhóm)</span>
              <select value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)}>
                <option value="">— Chưa phân công —</option>
                {(currentTeam?.members || []).map((m) => {
                  const blocked = m.role !== 'AGENT' || m.is_active === false;
                  return (
                    <option key={m.id} value={String(m.id)} disabled={blocked}>
                      {m.full_name} ({m.team_role}){blocked ? ' — không gán được' : ''}
                    </option>
                  );
                })}
              </select>
            </label>
            <label className="field"><span>Lý do phân công</span>
              <input value={assignReason} maxLength={500} onChange={(e) => setAssignReason(e.target.value)} />
            </label>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setAssignOpen(false)} disabled={assignBusy}>Hủy</button>
              <button className="btn-primary" onClick={submitAssign} disabled={assignBusy}>
                {assignBusy ? 'Đang lưu…' : 'Xác nhận phân công'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
