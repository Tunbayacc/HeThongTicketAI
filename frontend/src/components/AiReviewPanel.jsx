import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client.js';
import {
  AI_STATUS_LABELS, CATEGORY_LABELS, PRIORITY_LABELS,
  fmtDateTime, labelOf,
} from '../lib/labels.js';
import '../styles/ai.css';

function StatusBadge({ status }) {
  return (
    <span className={`badge ai-badge ai-badge--${(status || '').toLowerCase()}`}>
      {labelOf(AI_STATUS_LABELS, status)}
    </span>
  );
}

// Renders an AiResultOut.original_output by result type in friendly Vietnamese.
function OutputBody({ row }) {
  const o = row.original_output || {};
  if (row.result_type === 'CLASSIFICATION') {
    return (
      <p className="ai-meta">
        Đề xuất: nhóm {labelOf(CATEGORY_LABELS, o.category)} — ưu tiên{' '}
        {labelOf(PRIORITY_LABELS, o.priority)} — độ tin cậy {Math.round((row.confidence ?? 0) * 100)}%.
        {o.reason ? ` Lý do: ${o.reason}` : ''}
      </p>
    );
  }
  if (row.result_type === 'SUMMARY') {
    return (
      <div className="ai-note">
        <p><strong>Vấn đề:</strong> {o.problem || '—'}</p>
        {o.current_status ? <p><strong>Hiện trạng:</strong> {o.current_status}</p> : null}
        {Array.isArray(o.key_points) && o.key_points.length > 0 && (
          <p><strong>Điểm chính:</strong></p>
        )}
        {Array.isArray(o.key_points) && o.key_points.length > 0 && (
          <ul className="ai-keypoints">
            {o.key_points.map((k, i) => (
              <li key={`k-${i}`}>{k}</li>
            ))}
          </ul>
        )}
        {Array.isArray(o.next_steps) && o.next_steps.length > 0 && (
          <p className="ai-meta">Bước tiếp theo: {o.next_steps.join(' · ')}</p>
        )}
      </div>
    );
  }
  // DRAFT_REPLY
  return (
    <div className="ai-note">
      <p className="pre-wrap ai-draftbox">{o.draft || '—'}</p>
      {o.tone ? <p className="ai-meta">Giọng văn: {o.tone}</p> : null}
      {Array.isArray(o.warnings) && o.warnings.map((w, i) => (
        <p key={`w-${i}`} className="ai-meta">⚠ {w}</p>
      ))}
    </div>
  );
}

export default function AiReviewPanel({ ticketId, detail, onDraft, onTicketChanged }) {
  const [rows, setRows] = useState([]);       // newest-first AiResultOut list
  const [busy, setBusy] = useState(null);     // 'CLASSIFICATION'|'SUMMARY'|'DRAFT_REPLY' while generating
  const [acting, setActing] = useState(null); // result id while a review call is in flight
  const [error, setError] = useState(null);
  const [conflict, setConflict] = useState(null);
  const [edit, setEdit] = useState({});       // classify resultId -> {category, priority} overrides
  const [instruction, setInstruction] = useState('');

  const load = useCallback(async () => {
    try {
      const body = await api.get(`/api/tickets/${ticketId}/ai/results?page_size=20`);
      setRows(body.items || []);
      setError(null);
    } catch (err) {
      setError(err.message || 'Không tải được dữ liệu AI.');
    }
  }, [ticketId]);

  useEffect(() => { load(); }, [load]);

  const pendingClassify = rows.find(
    (r) => r.status === 'PENDING_REVIEW' && r.result_type === 'CLASSIFICATION',
  );
  const pendingOther = rows.filter(
    (r) => r.status === 'PENDING_REVIEW' && r.result_type !== 'CLASSIFICATION',
  );
  const history = rows.filter((r) => r.status !== 'PENDING_REVIEW');

  // Seed the override selects from the AI proposal whenever a new pending
  // classification appears (so the "chỉnh sửa" flow starts from the proposal).
  useEffect(() => {
    if (pendingClassify && !edit[pendingClassify.id]) {
      const o = pendingClassify.original_output || {};
      setEdit((prev) => ({
        ...prev,
        [pendingClassify.id]: {
          category: o.category || '',
          priority: o.priority || 'MEDIUM',
        },
      }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingClassify && pendingClassify.id]);

  function setField(id, field, value) {
    setEdit((prev) => ({ ...prev, [id]: { ...(prev[id] || {}), [field]: value } }));
  }

  function handleErr(err) {
    if (err.status === 409) {
      setConflict('Kết quả AI hoặc vé vừa được cập nhật ở nơi khác. Đã tải lại dữ liệu mới — vui lòng thử lại.');
      load();
      if (onTicketChanged) onTicketChanged();
    } else if (err.status === 403) {
      setError('Bạn không có quyền thực hiện thao tác này.');
    } else {
      setError(err.message || 'Thao tác AI thất bại. Vui lòng thử lại.');
    }
  }

  async function generate(type) {
    setBusy(type);
    setConflict(null);
    setError(null);
    try {
      const verb = type === 'CLASSIFICATION' ? 'classify'
        : type === 'SUMMARY' ? 'summarize' : 'draft';
      await api.post(
        `/api/tickets/${ticketId}/ai/${verb}`,
        type === 'DRAFT_REPLY' ? { instruction: instruction.trim() || null } : {},
      );
      setInstruction('');
      await load();
    } catch (err) {
      handleErr(err);
    } finally {
      setBusy(null);
    }
  }

  async function review(id, action) {
    setActing(id);
    setConflict(null);
    setError(null);
    try {
      const row = rows.find((r) => r.id === id);
      if (action === 'approve') {
        await api.post(`/api/ai/results/${id}/approve`, { version: detail.version });
      } else if (action === 'reject') {
        await api.post(`/api/ai/results/${id}/reject`, {});
      } else {
        // 'edit' -> submit the human's corrected classification for review.
        const o = (row && row.original_output) || {};
        const cur = edit[id] || { category: o.category || '', priority: o.priority || 'MEDIUM' };
        await api.post(`/api/ai/results/${id}/edit`, {
          reviewed_output: {
            category: cur.category,
            priority: cur.priority,
            confidence: o.confidence ?? null,
            reason: o.reason ?? null,
          },
          version: detail.version,
        });
      }
      await load();
      if (onTicketChanged) onTicketChanged();
    } catch (err) {
      handleErr(err);
    } finally {
      setActing(null);
    }
  }

  const editOf = (row) => {
    const o = (row && row.original_output) || {};
    const cur = edit[row.id] || { category: o.category || '', priority: o.priority || 'MEDIUM' };
    return cur;
  };

  const GenButton = ({ type, label }) => (
    <button
      type="button"
      className="ai-btn"
      disabled={busy !== null || acting !== null}
      onClick={() => generate(type)}
    >
      {busy === type ? 'Đang tạo…' : label}
    </button>
  );

  return (
    <section className="ai-panel" aria-label="Trợ lý AI">
      <h2>Trợ lý AI</h2>
      <p className="ai-sub text-muted">
        AI chỉ đề xuất — mọi kết quả đều cần nhân viên duyệt trước khi áp dụng.
      </p>

      <div className="ai-toolbar">
        <GenButton type="CLASSIFICATION" label="Phân loại tự động" />
        <GenButton type="SUMMARY" label="Tóm tắt AI" />
        <label className="field ai-instr">
          <span>Yêu cầu thêm cho bản nháp (tùy chọn)</span>
          <input
            value={instruction}
            maxLength={1000}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="VD: Nhã nhặn, ngắn gọn…"
          />
        </label>
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}
      {conflict && <p className="form-error" role="alert">{conflict}</p>}

      {pendingClassify && (() => {
        const cur = editOf(pendingClassify);
        const low = pendingClassify.low_confidence;
        return (
          <div className="ai-card">
            <div className="ai-card-head">
              <span className="ai-type">Phân loại — chờ duyệt</span>
              <StatusBadge status={pendingClassify.status} />
              {low && <span className="ai-low">⚠ Độ tin cậy thấp — hãy kiểm tra kỹ</span>}
            </div>
            <OutputBody row={pendingClassify} />
            <div className="ai-fields">
              <label className="field">
                <span>Phân loại (có thể chỉnh)</span>
                <select
                  value={cur.category}
                  onChange={(e) => setField(pendingClassify.id, 'category', e.target.value)}
                >
                  {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Ưu tiên (có thể chỉnh)</span>
                <select
                  value={cur.priority}
                  onChange={(e) => setField(pendingClassify.id, 'priority', e.target.value)}
                >
                  {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>
            </div>
            <div className="ai-review-actions">
              <button className="btn-primary" disabled={acting !== null}
                onClick={() => review(pendingClassify.id, 'approve')}>
                {acting === pendingClassify.id ? 'Đang lưu…' : 'Duyệt đề xuất'}
              </button>
              <button className="btn-secondary" disabled={acting !== null}
                onClick={() => review(pendingClassify.id, 'edit')}>
                {acting === pendingClassify.id ? 'Đang lưu…' : 'Lưu chỉnh sửa'}
              </button>
              <button className="btn-secondary" disabled={acting !== null}
                onClick={() => review(pendingClassify.id, 'reject')}>
                {acting === pendingClassify.id ? 'Đang lưu…' : 'Từ chối'}
              </button>
            </div>
          </div>
        );
      })()}

      {pendingOther.map((row) => (
        <div className="ai-card" key={row.id}>
          <div className="ai-card-head">
            <span className="ai-type">
              {row.result_type === 'SUMMARY' ? 'Tóm tắt AI' : 'Nháp trả lời AI'} — chờ duyệt
            </span>
            <StatusBadge status={row.status} />
          </div>
          <OutputBody row={row} />
          <div className="ai-review-actions">
            {row.result_type === 'DRAFT_REPLY' && (row.original_output?.draft) && (
              <button className="btn-primary" disabled={acting !== null}
                onClick={() => { if (onDraft) onDraft(row.original_output.draft); }}>
                Đưa vào ô trả lời
              </button>
            )}
            <button className="btn-secondary" disabled={acting !== null}
              onClick={() => review(row.id, 'approve')}>
              {acting === row.id ? 'Đang lưu…' : 'Duyệt'}
            </button>
            <button className="btn-secondary" disabled={acting !== null}
              onClick={() => review(row.id, 'reject')}>
              {acting === row.id ? 'Đang lưu…' : 'Từ chối'}
            </button>
          </div>
        </div>
      ))}

      {pendingClassify === undefined && pendingOther.length === 0 && history.length === 0 && (
        <p className="ai-empty">Chưa có kết quả AI nào cho vé này.</p>
      )}

      {history.length > 0 && (
        <>
          <p className="ai-meta">Kết quả đã xử lý gần đây:</p>
          <ul className="ai-list">
            {history.map((r) => (
              <li key={r.id} className="ai-history-item">
                <StatusBadge status={r.status} />
                <span>
                  {r.result_type === 'CLASSIFICATION' ? 'Phân loại'
                    : r.result_type === 'SUMMARY' ? 'Tóm tắt' : 'Nháp trả lời'}
                  {r.status === 'FAILED' && r.error_code ? ` — ${r.error_code}` : ''}
                  {r.status === 'EDITED' && r.reviewed_output?.category
                    ? ` → ${labelOf(CATEGORY_LABELS, r.reviewed_output.category)}` : ''}
                </span>
                <span className="text-muted">{fmtDateTime(r.reviewed_at || r.requested_at)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
