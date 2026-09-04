import { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client.js';

const ENTITY_TYPES = [
  { value: '', label: 'Tất cả đối tượng' },
  { value: 'USER', label: 'Người dùng (User)' },
  { value: 'TEAM', label: 'Nhóm hỗ trợ (Team)' },
  { value: 'SLA_POLICY', label: 'Chính sách SLA' },
  { value: 'TICKET', label: 'Vé hỗ trợ (Ticket)' },
  { value: 'AI', label: 'Trí tuệ nhân tạo (AI)' },
  { value: 'AUTH', label: 'Xác thực & Phiên (Auth)' },
];

const ACTION_LABELS = {
  USER_CREATED: 'Tạo người dùng',
  USER_UPDATED: 'Cập nhật người dùng',
  USER_DEACTIVATED: 'Vô hiệu hóa tài khoản',
  USER_ACTIVATED: 'Kích hoạt tài khoản',
  TEAM_CREATED: 'Tạo nhóm hỗ trợ',
  TEAM_UPDATED: 'Cập nhật nhóm hỗ trợ',
  TEAM_MEMBER_ADDED: 'Thêm thành viên nhóm',
  TEAM_MEMBER_REMOVED: 'Xóa thành viên nhóm',
  SLA_POLICY_CREATED: 'Tạo chính sách SLA',
  SLA_POLICY_UPDATED: 'Cập nhật chính sách SLA',
  TICKET_CREATED: 'Tạo vé hỗ trợ',
  TICKET_STATUS_CHANGED: 'Đổi trạng thái vé',
  TICKET_ASSIGNED: 'Phân công vé',
  TICKET_UPDATED: 'Cập nhật thông tin vé',
  AI_CLASSIFY: 'AI phân loại yêu cầu',
  AI_SUMMARIZE: 'AI tóm tắt nội dung',
  AI_DRAFT: 'AI tạo phản hồi nháp',
  AI_RESULT_APPROVED: 'Chấp thuận kết quả AI',
  AI_RESULT_REJECTED: 'Từ chối kết quả AI',
  AI_RESULT_EDITED: 'Chỉnh sửa gợi ý của AI',
  LOGIN_SUCCESS: 'Đăng nhập thành công',
  LOGIN_FAILED: 'Đăng nhập thất bại',
  LOGOUT: 'Đăng xuất hệ thống',
};

const ENTITY_LABELS = {
  USER: 'Người dùng',
  TEAM: 'Nhóm',
  SLA_POLICY: 'SLA',
  TICKET: 'Vé',
  AI: 'AI Agent',
  AUTH: 'Xác thực',
};

const OUTCOME_LABELS = { SUCCESS: 'Thành công', FAILURE: 'Thất bại' };

function labelAction(code) { return ACTION_LABELS[code] || code; }
function labelEntity(code) { return ENTITY_LABELS[code] || code; }
function labelOutcome(code) { return OUTCOME_LABELS[code] || code; }

export default function AdminAuditPage() {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [entityType, setEntityType] = useState('');
  const [actionQuery, setActionQuery] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');

  // Metadata Modal
  const [inspectLog, setInspectLog] = useState(null);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: '20' });
      if (entityType) params.set('entity_type', entityType);
      if (actionQuery.trim()) params.set('action', actionQuery.trim());
      if (fromDate) params.set('from', fromDate);
      if (toDate) params.set('to', toDate);

      const data = await api.get(`/api/audit-logs?${params.toString()}`);
      setLogs(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      setError(err.message || 'Không thể tải nhật ký hệ thống.');
    } finally {
      setLoading(false);
    }
  }, [page, entityType, actionQuery, fromDate, toDate]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  function resetFilters() {
    setEntityType('');
    setActionQuery('');
    setFromDate('');
    setToDate('');
    setPage(1);
  }

  // Summary counts
  const successCount = logs.filter((l) => l.outcome === 'SUCCESS').length;
  const failureCount = logs.filter((l) => l.outcome !== 'SUCCESS').length;

  return (
    <div className="admin-page-container">
      {/* Top KPI Summary Cards */}
      <div className="admin-summary-grid">
        <div className="admin-kpi-card">
          <div className="admin-kpi-content">
            <span className="admin-kpi-val">{total}</span>
            <span className="admin-kpi-lbl">Tổng bản ghi kiểm toán</span>
          </div>
          <div className="admin-kpi-icon admin-kpi-icon--blue">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
            </svg>
          </div>
        </div>

        <div className="admin-kpi-card">
          <div className="admin-kpi-content">
            <span className="admin-kpi-val" style={{ color: 'var(--color-success)' }}>
              {successCount} / {logs.length}
            </span>
            <span className="admin-kpi-lbl">Thao tác thành công (trang này)</span>
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
            <span className="admin-kpi-val" style={{ color: failureCount > 0 ? 'var(--color-danger)' : 'var(--color-text-muted)' }}>
              {failureCount}
            </span>
            <span className="admin-kpi-lbl">Sự kiện lỗi / Cảnh báo</span>
          </div>
          <div className={`admin-kpi-icon ${failureCount > 0 ? 'admin-kpi-icon--red' : 'admin-kpi-icon--amber'}`}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
        </div>

        <div className="admin-kpi-card">
          <div className="admin-kpi-content">
            <span className="admin-kpi-val" style={{ color: '#7c3aed' }}>
              6 Nhóm
            </span>
            <span className="admin-kpi-lbl">Phạm vi đối tượng kiểm soát</span>
          </div>
          <div className="admin-kpi-icon admin-kpi-icon--purple">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="12 2 2 7 12 12 22 7 12 2" />
              <polyline points="2 17 12 22 22 17" />
              <polyline points="2 12 12 17 22 12" />
            </svg>
          </div>
        </div>
      </div>

      {/* Header Info */}
      <div className="admin-toolbar" style={{ marginBottom: 'var(--space-3)' }}>
        <div>
          <h2 className="admin-toolbar-title">Nhật ký kiểm toán hệ thống (Audit Trail)</h2>
          <p className="admin-subtitle" style={{ margin: 0 }}>
            Lưu trữ bất biến toàn bộ thay đổi dữ liệu, phân quyền tài khoản, cấu hình SLA và phiên đăng nhập (SRS FR-AUD)
          </p>
        </div>
      </div>

      {/* Advanced Filter Toolbar */}
      <div className="admin-toolbar">
        <div className="admin-filters">
          <select
            className="admin-select"
            value={entityType}
            onChange={(e) => {
              setEntityType(e.target.value);
              setPage(1);
            }}
          >
            {ENTITY_TYPES.map((et) => (
              <option key={et.value} value={et.value}>{et.label}</option>
            ))}
          </select>

          <div className="admin-search-wrap" style={{ maxWidth: 280 }}>
            <span className="admin-search-icon">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </span>
            <input
              type="text"
              className="admin-input"
              style={{ width: '100%', paddingLeft: 34, paddingRight: actionQuery ? 28 : 12 }}
              placeholder="Tìm theo hành động (VD: USER_CREATED)…"
              value={actionQuery}
              onChange={(e) => {
                setActionQuery(e.target.value);
                setPage(1);
              }}
            />
            {actionQuery && (
              <button
                type="button"
                className="admin-search-clear"
                onClick={() => { setActionQuery(''); setPage(1); }}
                title="Xóa"
              >
                ✕
              </button>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
            <span>Từ ngày:</span>
            <input
              type="date"
              className="admin-input"
              style={{ padding: '6px 8px' }}
              value={fromDate}
              onChange={(e) => {
                setFromDate(e.target.value);
                setPage(1);
              }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
            <span>Đến ngày:</span>
            <input
              type="date"
              className="admin-input"
              style={{ padding: '6px 8px' }}
              value={toDate}
              onChange={(e) => {
                setToDate(e.target.value);
                setPage(1);
              }}
            />
          </div>

          <button
            type="button"
            className="btn-secondary btn-sm"
            onClick={resetFilters}
          >
            Đặt lại bộ lọc
          </button>
        </div>
      </div>

      {error && <div className="alert-error" style={{ marginBottom: 'var(--space-3)' }}>{error}</div>}

      {loading ? (
        <div className="state-loading">Đang tải nhật ký kiểm toán hệ thống…</div>
      ) : logs.length === 0 ? (
        <div className="empty-state">
          <p style={{ margin: 0 }}>Không tìm thấy bản ghi nhật ký kiểm toán nào phù hợp với bộ lọc hiện tại.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <div style={{ overflowX: 'auto' }}>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>THỜI GIAN</th>
                  <th>NGƯỜI THỰC HIỆN</th>
                  <th>HÀNH ĐỘNG</th>
                  <th>ĐỐI TƯỢNG</th>
                  <th>KẾT QUẢ</th>
                  <th>ĐỊA CHỈ IP</th>
                  <th style={{ textAlign: 'right' }}>CHI TIẾT</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => {
                  const isSuccess = log.outcome === 'SUCCESS';
                  const isSystem = !log.actor_id && !log.actor_name;

                  return (
                    <tr key={log.id}>
                      <td style={{ whiteSpace: 'nowrap', fontSize: 'var(--font-size-xs)', fontFamily: 'var(--font-mono)', color: 'var(--color-text-secondary)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--color-text-muted)' }}>
                            <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
                          </svg>
                          {new Date(log.created_at).toLocaleString('vi-VN')}
                        </div>
                      </td>

                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span
                            className="user-avatar-sm"
                            style={{
                              width: 26,
                              height: 26,
                              fontSize: 10,
                              background: isSystem ? '#f1f5f9' : 'var(--color-primary-subtle)',
                              color: isSystem ? 'var(--color-text-muted)' : 'var(--color-primary-text)',
                            }}
                          >
                            {isSystem ? '⚙️' : (log.actor_name ? log.actor_name.charAt(0).toUpperCase() : 'U')}
                          </span>
                          <span style={{ fontWeight: 600, fontSize: 'var(--font-size-sm)' }}>
                            {log.actor_name || (log.actor_id ? `User #${log.actor_id}` : 'Hệ thống (System)')}
                          </span>
                        </div>
                      </td>

                      <td>
                        <span style={{ fontWeight: 600, color: 'var(--color-text)', display: 'block' }}>
                          {labelAction(log.action)}
                        </span>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--color-text-muted)' }}>
                          {log.action}
                        </span>
                      </td>

                      <td>
                        <span className="badge" style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', color: 'var(--color-text-secondary)' }}>
                          {labelEntity(log.entity_type)}
                          {log.entity_id ? ` #${log.entity_id}` : ''}
                        </span>
                      </td>

                      <td>
                        <span className={`badge ${isSuccess ? 'badge-active' : 'badge-admin'}`}>
                          <span className={`status-dot ${isSuccess ? 'status-dot-active' : 'status-dot-inactive'}`} />
                          {labelOutcome(log.outcome)}
                        </span>
                      </td>

                      <td style={{ fontSize: 'var(--font-size-xs)', fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}>
                        {log.ip_address || '—'}
                      </td>

                      <td style={{ textAlign: 'right' }}>
                        <button
                          type="button"
                          className="btn-secondary btn-sm"
                          onClick={() => setInspectLog(log)}
                        >
                          Xem Metadata
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="admin-pagination">
            <span>Tổng cộng: {total} sự kiện kiểm toán · Trang {page} / {totalPages}</span>
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

      {/* Modal: Inspect Metadata */}
      {inspectLog && (
        <div className="admin-modal-backdrop" onClick={() => setInspectLog(null)}>
          <div className="admin-modal-dialog" style={{ maxWidth: 640 }} onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2 className="admin-modal-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                Chi tiết sự kiện kiểm toán #{inspectLog.id}
              </h2>
              <button type="button" className="admin-modal-close" onClick={() => setInspectLog(null)}>✕</button>
            </div>
            <div className="admin-modal-body">
              <div className="audit-meta-grid">
                <span className="text-muted">Thời gian ghi nhận:</span>
                <span style={{ fontWeight: 600 }}>{new Date(inspectLog.created_at).toLocaleString('vi-VN')}</span>

                <span className="text-muted">Hành động:</span>
                <span>
                  <strong>{labelAction(inspectLog.action)}</strong>{' '}
                  <code style={{ fontSize: 11, background: 'var(--color-surface)', padding: '1px 4px', borderRadius: 3, border: '1px solid var(--color-border)' }}>
                    {inspectLog.action}
                  </code>
                </span>

                <span className="text-muted">Người thực hiện:</span>
                <span>{inspectLog.actor_name || 'System'} (ID: {inspectLog.actor_id || 'N/A'})</span>

                <span className="text-muted">Đối tượng chịu tác động:</span>
                <span>{labelEntity(inspectLog.entity_type)} {inspectLog.entity_id ? `(ID: ${inspectLog.entity_id})` : ''}</span>

                <span className="text-muted">Kết quả xử lý:</span>
                <span>
                  <span className={`badge ${inspectLog.outcome === 'SUCCESS' ? 'badge-active' : 'badge-admin'}`}>
                    {labelOutcome(inspectLog.outcome)}
                  </span>
                </span>

                <span className="text-muted">Địa chỉ IP thực hiện:</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>{inspectLog.ip_address || '—'}</span>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: 'var(--space-2) 0 var(--space-1)' }}>
                  <strong style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Dữ liệu Metadata chi tiết (JSON Payload):
                  </strong>
                  {inspectLog.metadata && (
                    <button
                      type="button"
                      className="btn-ghost btn-sm"
                      style={{ fontSize: 11, padding: '2px 6px' }}
                      onClick={() => {
                        navigator.clipboard.writeText(JSON.stringify(inspectLog.metadata, null, 2));
                      }}
                    >
                      Sao chép JSON
                    </button>
                  )}
                </div>
                <pre className="audit-json-viewer">
                  {inspectLog.metadata ? JSON.stringify(inspectLog.metadata, null, 2) : '// Không có payload metadata kèm theo'}
                </pre>
              </div>
            </div>
            <div className="admin-modal-footer">
              <button type="button" className="btn-secondary" onClick={() => setInspectLog(null)}>Đóng</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
