import { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client.js';

const ENTITY_TYPES = [
  { value: '', label: 'Tất cả đối tượng' },
  { value: 'USER', label: 'Người dùng (USER)' },
  { value: 'TEAM', label: 'Nhóm hỗ trợ (TEAM)' },
  { value: 'SLA_POLICY', label: 'Chính sách SLA' },
  { value: 'TICKET', label: 'Vé hỗ trợ (TICKET)' },
  { value: 'AI', label: 'Trí tuệ nhân tạo (AI)' },
  { value: 'AUTH', label: 'Xác thực / Phiên (AUTH)' },
];

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

  return (
    <div>
      <div className="admin-toolbar">
        <div>
          <h2 style={{ margin: 0, fontSize: '1.2rem' }}>Nhật ký kiểm toán hệ thống (Audit Logs)</h2>
          <p className="admin-subtitle">
            Ghi nhận bất biến mọi thay đổi phân quyền, dữ liệu người dùng, nhóm và SLA (SRS FR-AUD)
          </p>
        </div>
      </div>

      {/* Filter toolbar */}
      <div className="admin-toolbar" style={{ background: 'var(--color-surface)', padding: 'var(--space-3)', borderRadius: 'var(--radius-sm)' }}>
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

          <input
            type="text"
            className="admin-input"
            placeholder="Tìm hành động (VD: USER_CREATED...)"
            value={actionQuery}
            onChange={(e) => {
              setActionQuery(e.target.value);
              setPage(1);
            }}
          />

          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)', fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
            <span>Từ:</span>
            <input
              type="date"
              className="admin-input"
              value={fromDate}
              onChange={(e) => {
                setFromDate(e.target.value);
                setPage(1);
              }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)', fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
            <span>Đến:</span>
            <input
              type="date"
              className="admin-input"
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
            Đặt lại
          </button>
        </div>
      </div>

      {error && <div className="alert-error" style={{ marginBottom: 'var(--space-3)' }}>{error}</div>}

      {loading ? (
        <div className="state-loading">Đang tải nhật ký kiểm toán...</div>
      ) : logs.length === 0 ? (
        <div className="state-empty">Không tìm thấy bản ghi nhật ký kiểm toán nào.</div>
      ) : (
        <>
          <div className="admin-table-container">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Thời gian</th>
                  <th>Người thực hiện</th>
                  <th>Hành động</th>
                  <th>Đối tượng</th>
                  <th>Kết quả</th>
                  <th>Địa chỉ IP</th>
                  <th style={{ textAlign: 'right' }}>Chi tiết</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td style={{ whiteSpace: 'nowrap', fontSize: '0.8rem' }}>
                      {new Date(log.created_at).toLocaleString('vi-VN')}
                    </td>
                    <td>
                      <strong>{log.actor_name || (log.actor_id ? 'Tài khoản' : 'Hệ thống (System)')}</strong>
                    </td>
                    <td>
                      <code style={{ fontSize: '0.8rem', background: 'var(--color-surface)', padding: '2px 4px', borderRadius: '4px' }}>
                        {log.action}
                      </code>
                    </td>
                    <td>
                      <span className="badge" style={{ background: 'var(--color-surface)' }}>
                        {log.entity_type}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${log.outcome === 'SUCCESS' ? 'badge-active' : 'badge-admin'}`}>
                        {log.outcome}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                      {log.ip_address || '—'}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        type="button"
                        className="btn-secondary btn-sm"
                        onClick={() => setInspectLog(log)}
                      >
                        Metadata
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="admin-pagination">
            <span>Tổng cộng: {total} bản ghi</span>
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

      {/* Modal: Inspect Metadata */}
      {inspectLog && (
        <div className="admin-modal-backdrop" onClick={() => setInspectLog(null)}>
          <div className="admin-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2 className="admin-modal-title">Chi tiết bản ghi: {inspectLog.action}</h2>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setInspectLog(null)}>✕</button>
            </div>
            <div className="admin-modal-body">
              <div style={{ fontSize: 'var(--font-size-sm)', display: 'grid', gridTemplateColumns: '120px 1fr', gap: 'var(--space-1)' }}>
                <strong>Thời gian:</strong> <span>{new Date(inspectLog.created_at).toLocaleString('vi-VN')}</span>
                <strong>Người thực hiện:</strong> <span>{inspectLog.actor_name || 'System'} ({inspectLog.actor_id || 'N/A'})</span>
                <strong>Đối tượng:</strong> <span>{inspectLog.entity_type} {inspectLog.entity_id ? `(${inspectLog.entity_id})` : ''}</span>
                <strong>Kết quả:</strong> <span>{inspectLog.outcome}</span>
                <strong>Địa chỉ IP:</strong> <span>{inspectLog.ip_address || '—'}</span>
              </div>
              <div>
                <strong style={{ fontSize: 'var(--font-size-sm)', display: 'block', margin: 'var(--space-2) 0 var(--space-1)' }}>
                  Metadata JSON:
                </strong>
                <pre
                  style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-sm)',
                    padding: 'var(--space-3)',
                    fontSize: '0.8rem',
                    overflowX: 'auto',
                    margin: 0,
                  }}
                >
                  {inspectLog.metadata ? JSON.stringify(inspectLog.metadata, null, 2) : 'null'}
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
