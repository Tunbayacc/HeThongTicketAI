import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, triggerDownload } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import {
  CATEGORY_LABELS, PRIORITY_LABELS, STATUS_LABELS, TEAM_ROLE_LABELS, VISIBILITY_LABELS,
  fmtDateTime, labelOf,
} from '../lib/labels.js';
import AiReviewPanel from '../components/AiReviewPanel.jsx';
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

const ALL_STATUSES = ['OPEN', 'IN_PROGRESS', 'PENDING', 'RESOLVED', 'CLOSED'];

function fmtBytes(n) {
  if (n == null) return '—';
  if (n < 1024) return `${n} B`;
  return `${(n / 1024).toFixed(1)} KB`;
}

const FIELD_NAMES = {
  subject: 'tiêu đề',
  description: 'mô tả',
  priority: 'mức ưu tiên',
  category: 'phân loại',
  status: 'trạng thái',
  assigned_to: 'người phụ trách',
  team_id: 'nhóm hỗ trợ',
};

function formatFieldValue(field, val) {
  if (val == null || val === '') return '—';
  if (field === 'priority') return labelOf(PRIORITY_LABELS, val);
  if (field === 'category') return labelOf(CATEGORY_LABELS, val);
  if (field === 'status') return labelOf(STATUS_LABELS, val);
  return String(val);
}

function eventText(h) {
  switch (h.event_type) {
    case 'STATUS_CHANGED':
      return `Chuyển trạng thái: ${labelOf(STATUS_LABELS, h.old_value)} → ${labelOf(STATUS_LABELS, h.new_value)}`;
    case 'ASSIGNED':
      return 'Cập nhật phân công xử lý';
    case 'COMMENT_ADDED':
      return 'Thêm bình luận mới';
    case 'ATTACHMENT_ADDED':
      return 'Đính kèm tệp tin mới';
    case 'FIELD_UPDATED': {
      const field = FIELD_NAMES[h.field_name] || h.field_name || 'thông tin';
      return `Thay đổi ${field}: ${formatFieldValue(h.field_name, h.old_value)} → ${formatFieldValue(h.field_name, h.new_value)}`;
    }
    default:
      return `${h.event_type}${h.field_name ? ` (${h.field_name})` : ''}`;
  }
}

export default function TicketDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const canAssign = user?.role === 'MANAGER' || user?.role === 'ADMIN';

  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [actionError, setActionError] = useState(null);

  // status dialog
  const [statusDialog, setStatusDialog] = useState(null);
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
  const fileInputRef = useRef(null);

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
      setLoadError(err.message || 'Không thể tải thông tin vé hỗ trợ.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDetail();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Ghép và sắp xếp toàn bộ hoạt động theo thứ tự mới nhất lên trên cùng
  const timelineItems = useMemo(() => {
    if (!detail) return [];
    const comments = (detail.comments || []).map((c) => ({
      type: 'comment',
      data: c,
      time: new Date(c.created_at).getTime(),
    }));
    const attachments = (detail.attachments || []).filter((a) => !a.comment).map((a) => ({
      type: 'attachment',
      data: a,
      time: new Date(a.created_at).getTime(),
    }));
    const history = (detail.history || []).map((h) => ({
      type: 'history',
      data: h,
      time: new Date(h.created_at).getTime(),
    }));
    return [...comments, ...attachments, ...history].sort((a, b) => b.time - a.time);
  }, [detail]);

  // ---- status change -------------------------------------------------------
  const submitStatus = useCallback(async () => {
    const reopen = (detail?.status === 'RESOLVED' || detail?.status === 'CLOSED') && statusDialog === 'IN_PROGRESS';
    if (reopen && !statusReason.trim()) {
      setActionError('Vui lòng nhập lý do khi mở lại vé.');
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
        setActionError(err.message || 'Không thể tải danh sách nhóm hỗ trợ.');
        return;
      }
    }
    setAssignOpen(true);
  }, [teams, teamId, detail]);

  const submitAssign = useCallback(async () => {
    if (!teamId) { setActionError('Vui lòng chọn nhóm hỗ trợ.'); return; }
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
    const trimmed = content.trim();
    if (!trimmed && files.length === 0) {
      setActionError('Vui lòng nhập nội dung bình luận hoặc chọn tệp đính kèm.');
      return;
    }
    if (files.length > MAX_FILES) {
      setActionError(`Mỗi phản hồi tối đa ${MAX_FILES} tệp đính kèm.`);
      return;
    }
    setCommentBusy(true);
    setActionError(null);
    try {
      const fd = new FormData();
      fd.append('content', trimmed || 'Đính kèm tệp');
      fd.append('visibility', visibility);
      files.forEach((f) => fd.append('files', f));
      const body = await api.postForm(`/api/tickets/${id}/comments`, fd);
      setDetail(body);
      setContent('');
      setFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = '';
      setVisibility('PUBLIC');
    } catch (err) {
      handleActionError(err);
    } finally {
      setCommentBusy(false);
    }
  }, [id, content, visibility, files]);

  function handleActionError(err) {
    if (err.error_code === 'VERSION_CONFLICT' || err.status === 409) {
      setActionError('Vé vừa được người khác cập nhật. Hệ thống đã tải lại dữ liệu mới nhất — vui lòng thử lại.');
      loadDetail();
    } else if (err.status === 403) {
      setActionError('Bạn không có quyền thực hiện thao tác này.');
    } else if (err.error_code === 'INVALID_STATUS_TRANSITION') {
      setActionError('Không thể chuyển sang trạng thái này theo quy trình.');
    } else if (err.error_code === 'ASSIGNEE_NOT_IN_TEAM') {
      setActionError('Người được phân công không thuộc nhóm hỗ trợ đã chọn.');
    } else {
      setActionError(err.message || 'Thao tác thất bại. Vui lòng thử lại.');
    }
  }

  async function download(att) {
    try {
      const blob = await api.fetchBlob(`/api/attachments/${att.id}/download`);
      triggerDownload(blob, att.original_name);
    } catch (err) {
      setActionError(err.message || 'Không thể tải tệp tin.');
    }
  }

  if (loading) return <section className="page"><p className="text-muted state-loading">Đang tải chi tiết vé…</p></section>;
  if (loadError) {
    return (
      <section className="page">
        <p className="form-error" role="alert">{loadError}</p>
        <button className="btn-secondary" style={{ marginTop: 'var(--space-3)' }} onClick={() => navigate('/app/tickets')}>
          ← Quay lại danh sách vé
        </button>
      </section>
    );
  }

  const currentTeam = teams.find((t) => String(t.id) === String(teamId));

  return (
    <section className="page ticket-detail">
      {/* ================================================================
          CỘT TRÁI — Không gian hội thoại và xử lý
          ================================================================ */}
      <div className="ticket-main">
        <div className="ticket-nav-bar">
          <Link to="/app/tickets" className="back-btn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            <span>Quay lại danh sách vé</span>
          </Link>
        </div>

        <header>
          <div className="ticket-title-row">
            <h1>{detail.subject}</h1>
            <span className="code-cell code-badge">{detail.ticket_code}</span>
          </div>
          <div className="badge-row" style={{ marginTop: 'var(--space-2)' }}>
            <span className={`badge badge--${(detail.status || '').toLowerCase()}`}>{labelOf(STATUS_LABELS, detail.status)}</span>
            <span className={`badge badge--${(detail.priority || '').toLowerCase()}`}>{labelOf(PRIORITY_LABELS, detail.priority)}</span>
            <span className="badge">{labelOf(CATEGORY_LABELS, detail.category)}</span>
          </div>
        </header>

        {actionError && <p className="form-error" role="alert">{actionError}</p>}

        {/* Nội dung mô tả ban đầu */}
        <section className="ticket-description">
          <h2>Mô tả yêu cầu từ khách hàng</h2>
          <p className="pre-wrap" style={{ margin: 'var(--space-2) 0' }}>{detail.description}</p>
          <p className="text-muted text-xs" style={{ margin: 0 }}>
            Người gửi: <strong>{detail.requester_name}</strong> ({detail.requester_email}) · Thời gian gửi: {fmtDateTime(detail.created_at)}
          </p>
        </section>

        {/* Khung soạn thảo phản hồi */}
        <section className="composer">
          <div className="composer-header">
            <button
              type="button"
              className={`composer-tab ${visibility === 'PUBLIC' ? 'active' : ''}`}
              onClick={() => setVisibility('PUBLIC')}
            >
              Phản hồi công khai (Gửi khách hàng)
            </button>
            <button
              type="button"
              className={`composer-tab ${visibility === 'INTERNAL' ? 'active active-internal' : ''}`}
              onClick={() => setVisibility('INTERNAL')}
            >
              Ghi chú nội bộ (Chỉ nhân viên xem)
            </button>
          </div>
          <div className="composer-body">
            <textarea
              rows={4}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder={visibility === 'PUBLIC' ? 'Nhập nội dung phản hồi gửi tới khách hàng…' : 'Nhập ghi chú nội bộ (khách hàng sẽ không thấy nội dung này)…'}
            />
            <div className="composer-footer" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
                <label className="field" style={{ flex: 1, maxWidth: 420 }}>
                  <span className="text-xs">Tệp đính kèm / ảnh chụp (PNG, JPG, WEBP, GIF, PDF, DOCX, TXT — tối đa {MAX_FILES} tệp)</span>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.png,.jpg,.jpeg,.webp,.gif,.txt,.docx,image/*"
                    onChange={(e) => setFiles(Array.from(e.target.files || []))}
                  />
                </label>
                <button className="btn-primary" disabled={commentBusy} onClick={submitComment}>
                  {commentBusy ? 'Đang gửi…' : visibility === 'PUBLIC' ? 'Gửi phản hồi khách hàng' : 'Lưu ghi chú nội bộ'}
                </button>
              </div>

              {files.length > 0 && (
                <div className="selected-files-list">
                  {files.map((file, idx) => {
                    const isImg = file.type.startsWith('image/') || /\.(png|jpe?g|webp|gif)$/i.test(file.name);
                    return (
                      <div key={idx} className="selected-file-chip">
                        <span>{isImg ? '🖼️' : '📎'} {file.name}</span>
                        <span className="text-muted text-xs">({fmtBytes(file.size)})</span>
                        <button
                          type="button"
                          onClick={() => {
                            const remaining = files.filter((_, i) => i !== idx);
                            setFiles(remaining);
                            if (remaining.length === 0 && fileInputRef.current) {
                              fileInputRef.current.value = '';
                            }
                          }}
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
          </div>
        </section>

        {/* Dòng thời gian hoạt động (Mới nhất lên trên cùng) */}
        <section className="timeline">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-3)' }}>
            <h2 style={{ margin: 0 }}>Dòng thời gian hoạt động</h2>
            <span className="text-muted text-xs">Mới nhất ở trên</span>
          </div>

          <ul className="timeline-list">
            {timelineItems.length === 0 && (
              <li className="text-muted text-xs">Chưa có hoạt động nào được ghi nhận.</li>
            )}

            {timelineItems.map((item) => {
              if (item.type === 'comment') {
                const c = item.data;
                return (
                  <li key={`c-${c.id}`} className={`timeline-comment ${c.visibility === 'INTERNAL' ? 'comment-internal' : ''}`}>
                    <div className="comment-meta">
                      <strong>{c.author_name || 'Hệ thống'}</strong>
                      <span className={`badge badge--${(c.visibility || '').toLowerCase()}`}>
                        {labelOf(VISIBILITY_LABELS, c.visibility)}
                      </span>
                      <span className="text-muted text-xs">{fmtDateTime(c.created_at)}</span>
                    </div>
                    <p className="pre-wrap" style={{ margin: 'var(--space-1) 0 0' }}>{c.content}</p>
                  </li>
                );
              }

              if (item.type === 'attachment') {
                const a = item.data;
                const isImg = (a.mime_type && a.mime_type.startsWith('image/')) ||
                  /\.(png|jpe?g|webp|gif)$/i.test(a.original_name);
                return (
                  <li key={`a-${a.id}`} className="timeline-attachment">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                      <button className="linklike" onClick={() => download(a)} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <span>{isImg ? '🖼️' : '📎'}</span>
                        <span style={{ fontWeight: 500 }}>{a.original_name}</span>
                      </button>
                      <span className="text-muted text-xs">({fmtBytes(a.size_bytes)})</span>
                      <button
                        type="button"
                        className="btn-secondary btn-sm"
                        style={{ padding: '2px 8px', fontSize: '11px' }}
                        onClick={() => download(a)}
                      >
                        Tải về
                      </button>
                    </div>
                  </li>
                );
              }

              if (item.type === 'history') {
                const h = item.data;
                return (
                  <li key={`h-${h.id}`} className="timeline-event">
                    <span className="event-icon">○</span>
                    <span className="event-text">{eventText(h)}</span>
                    <span className="text-muted text-xs">{fmtDateTime(h.created_at)}</span>
                    {h.reason && <span className="text-muted text-xs">— Lý do: {h.reason}</span>}
                  </li>
                );
              }

              return null;
            })}
          </ul>
        </section>
      </div>

      {/* ================================================================
          CỘT PHẢI — Thanh ngữ cảnh, thông tin và trợ lý AI
          ================================================================ */}
      <div className="ticket-sidebar">
        {/* Khối thông tin chi tiết */}
        <div className="ticket-meta-panel">
          <div className="ticket-meta-header">
            <h3>Chi tiết vé</h3>
            <button className="btn-secondary btn-sm" onClick={() => { setActionError(null); setEditOpen(true); }}>Chỉnh sửa</button>
          </div>
          <div className="ticket-meta-body">
            <div className="meta-grid">
              <span className="meta-label">Trạng thái</span>
              <span className="meta-value"><span className={`badge badge--${(detail.status || '').toLowerCase()}`}>{labelOf(STATUS_LABELS, detail.status)}</span></span>

              <span className="meta-label">Mức ưu tiên</span>
              <span className="meta-value"><span className={`badge badge--${(detail.priority || '').toLowerCase()}`}>{labelOf(PRIORITY_LABELS, detail.priority)}</span></span>

              <span className="meta-label">Phân loại</span>
              <span className="meta-value">{labelOf(CATEGORY_LABELS, detail.category)}</span>

              <span className="meta-label">Khách hàng</span>
              <span className="meta-value">{detail.requester_name}</span>

              <span className="meta-label">Email liên hệ</span>
              <span className="meta-value text-sm">{detail.requester_email}</span>

              <span className="meta-label">Nhóm xử lý</span>
              <span className="meta-value">{detail.team_name || 'Chưa gán'}</span>

              <span className="meta-label">Người phụ trách</span>
              <span className="meta-value">{detail.assignee_name || 'Chưa phân công'}</span>

              {detail.resolution_due_at && (
                <>
                  <span className="meta-label">Hạn giải quyết (SLA)</span>
                  <span className="meta-value" style={{ fontWeight: 600, color: 'var(--color-primary)' }}>
                    {fmtDateTime(detail.resolution_due_at)}
                  </span>
                </>
              )}

              <span className="meta-label">Cập nhật lúc</span>
              <span className="meta-value text-xs">{fmtDateTime(detail.updated_at)}</span>
            </div>
          </div>

          {detail.needs_reassignment && (
            <div className="ticket-actions-bar">
              <p className="form-error needs-reassign" role="alert" style={{ margin: 0, flex: 1, fontSize: 'var(--font-size-xs)' }}>
                ⚠ Cần phân công lại: Nhân viên phụ trách trước đó đã bị vô hiệu hóa tài khoản.
                {canAssign && <button className="btn-secondary btn-sm" type="button" style={{ marginLeft: 'var(--space-2)' }} onClick={openAssign}>Phân công lại</button>}
              </p>
            </div>
          )}

          <div className="ticket-actions-bar">
            {canAssign && <button className="btn-secondary btn-sm" onClick={openAssign}>Phân công người xử lý</button>}
          </div>
        </div>

        {/* Khối chuyển trạng thái */}
        <div className="status-transitions">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-1)' }}>
            <span className="status-transitions-label">Chuyển trạng thái vé</span>
            <span className="text-muted text-xs">Hiện tại: <strong>{labelOf(STATUS_LABELS, detail.status)}</strong></span>
          </div>
          <div className="status-transitions-row">
            {ALL_STATUSES.map((target) => {
              const isCurrent = target === detail.status;
              const isAllowed = (NEXT_STATUSES[detail.status] || []).includes(target);
              const label = labelOf(STATUS_LABELS, target);

              if (isCurrent) {
                return (
                  <button
                    key={target}
                    className="btn-secondary btn-sm status-btn--current"
                    type="button"
                    disabled
                    title="Trạng thái hiện tại của vé"
                  >
                    ● {label} (Hiện tại)
                  </button>
                );
              }

              return (
                <button
                  key={target}
                  className={`btn-secondary btn-sm ${!isAllowed ? 'status-btn--disallowed' : ''}`}
                  type="button"
                  disabled={!isAllowed}
                  title={
                    isAllowed
                      ? `Chuyển sang ${label}`
                      : `Không thể chuyển trực tiếp từ "${labelOf(STATUS_LABELS, detail.status)}" sang "${label}" theo quy trình`
                  }
                  onClick={() => {
                    if (!isAllowed) return;
                    setActionError(null);
                    setStatusReason('');
                    setStatusDialog(target);
                  }}
                >
                  Chuyển sang {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Trợ lý AI */}
        <AiReviewPanel
          ticketId={id}
          detail={detail}
          onDraft={(text) => { setContent(text); setVisibility('PUBLIC'); setActionError(null); }}
          onTicketChanged={loadDetail}
        />
      </div>

      {/* ================================================================
          CÁC HỘP THOẠI (MODALS)
          ================================================================ */}

      {/* Hộp thoại đổi trạng thái */}
      {statusDialog && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Xác nhận đổi trạng thái" onClick={() => setStatusDialog(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Chuyển trạng thái sang "{labelOf(STATUS_LABELS, statusDialog)}"?</h2>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setStatusDialog(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p className="text-muted text-sm" style={{ margin: 0 }}>
                Mã vé: <span className="code-badge">{detail.ticket_code}</span> — Trạng thái hiện tại: <span className={`badge badge--${(detail.status || '').toLowerCase()}`}>{labelOf(STATUS_LABELS, detail.status)}</span>
              </p>
              <div className="form-group" style={{ marginTop: 'var(--space-2)' }}>
                <label className="form-label">
                  Lý do thay đổi {(detail.status === 'RESOLVED' || detail.status === 'CLOSED') && statusDialog === 'IN_PROGRESS' ? '(bắt buộc khi mở lại vé)' : '(tùy chọn)'}
                </label>
                <textarea
                  className="admin-input"
                  rows={3}
                  value={statusReason}
                  onChange={(e) => setStatusReason(e.target.value)}
                  placeholder="Nhập lý do chuyển trạng thái..."
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setStatusDialog(null)} disabled={statusBusy}>Hủy bỏ</button>
              <button className="btn-primary" onClick={submitStatus} disabled={statusBusy}>
                {statusBusy ? 'Đang cập nhật…' : 'Xác nhận chuyển'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Hộp thoại chỉnh sửa thông tin vé */}
      {editOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Chỉnh sửa thông tin vé" onClick={() => setEditOpen(false)}>
          <div className="modal" style={{ maxWidth: 580 }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Chỉnh sửa thông tin vé #{detail.ticket_code}</h2>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setEditOpen(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Tiêu đề vé *</label>
                <input
                  className="admin-input"
                  value={editForm.subject}
                  maxLength={200}
                  onChange={(e) => setEditForm((f) => ({ ...f, subject: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Mô tả chi tiết *</label>
                <textarea
                  className="admin-input"
                  rows={4}
                  value={editForm.description}
                  maxLength={20000}
                  onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
                />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                <div className="form-group">
                  <label className="form-label">Phân loại yêu cầu</label>
                  <select
                    className="admin-select"
                    value={editForm.category}
                    onChange={(e) => setEditForm((f) => ({ ...f, category: e.target.value }))}
                  >
                    {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Mức độ ưu tiên</label>
                  <select
                    className="admin-select"
                    value={editForm.priority}
                    onChange={(e) => setEditForm((f) => ({ ...f, priority: e.target.value }))}
                  >
                    {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Lý do chỉnh sửa (tùy chọn)</label>
                <input
                  className="admin-input"
                  value={editReason}
                  maxLength={500}
                  onChange={(e) => setEditReason(e.target.value)}
                  placeholder="Nhập lý do thay đổi..."
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setEditOpen(false)} disabled={editBusy}>Hủy bỏ</button>
              <button className="btn-primary" onClick={submitEdit} disabled={editBusy}>
                {editBusy ? 'Đang lưu…' : 'Lưu thay đổi'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Hộp thoại phân công vé */}
      {assignOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Phân công vé xử lý" onClick={() => setAssignOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--color-primary)' }}>
                  <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
                Phân công vé xử lý
              </h2>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setAssignOpen(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Nhóm hỗ trợ tiếp nhận *</label>
                <select
                  className="admin-select"
                  value={teamId}
                  onChange={(e) => { setTeamId(e.target.value); setAssigneeId(''); }}
                >
                  <option value="">— Chọn nhóm hỗ trợ —</option>
                  {teams.map((t) => <option key={t.id} value={String(t.id)}>{t.name}</option>)}
                </select>
                <span className="form-hint">Chỉ định nhóm chuyên trách để tiếp nhận và điều phối vé này.</span>
              </div>

              <div className="form-group">
                <label className="form-label">Nhân viên phụ trách (tùy chọn)</label>
                <select
                  className="admin-select"
                  value={assigneeId}
                  onChange={(e) => setAssigneeId(e.target.value)}
                >
                  <option value="">— Chưa phân công nhân viên cụ thể —</option>
                  {(currentTeam?.members || []).map((m) => {
                    const blocked = m.role !== 'AGENT' || m.is_active === false;
                    return (
                      <option key={m.id} value={String(m.id)} disabled={blocked}>
                        {m.full_name} ({labelOf(TEAM_ROLE_LABELS, m.team_role)}){blocked ? ' — không thể gán' : ''}
                      </option>
                    );
                  })}
                </select>
                <span className="form-hint">Nhân viên được gán phải đang hoạt động trong nhóm hỗ trợ đã chọn.</span>
              </div>

              <div className="form-group">
                <label className="form-label">Ghi chú / Lý do phân công (tùy chọn)</label>
                <input
                  className="admin-input"
                  value={assignReason}
                  maxLength={500}
                  onChange={(e) => setAssignReason(e.target.value)}
                  placeholder="Ghi chú thêm về lý do hoặc yêu cầu xử lý..."
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setAssignOpen(false)} disabled={assignBusy}>Hủy bỏ</button>
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
