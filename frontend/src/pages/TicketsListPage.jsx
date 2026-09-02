import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client.js';
import {
  CATEGORY_LABELS, PRIORITY_LABELS, STATUS_LABELS, fmtDateTime, labelOf,
} from '../lib/labels.js';
import '../styles/tickets.css';

const PAGE_SIZE = 10;

export default function TicketsListPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);          // TicketListItem[]
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [status, setStatus] = useState('');      // '' = all
  const [q, setQ] = useState('');
  const [assignedToMe, setAssignedToMe] = useState(false);
  const [submittedQ, setSubmittedQ] = useState('');

  async function load(nextPage = page, filters = {}) {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        page: String(nextPage),
        page_size: String(PAGE_SIZE),
      });
      const st = filters.status ?? status;
      const query = filters.q ?? submittedQ;
      const mine = filters.assignedToMe ?? assignedToMe;
      if (st) params.set('status', st);
      if (query) params.set('q', query);
      if (mine) params.set('assigned_to_me', 'true');
      const body = await api.get(`/api/tickets?${params.toString()}`);
      setRows(body.items);
      setTotal(body.total);
      setPage(nextPage);
    } catch (err) {
      setError(err.message || 'Không thể tải danh sách vé.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(1, { status, q: submittedQ, assignedToMe });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, submittedQ, assignedToMe]);

  function applySearch(e) {
    e.preventDefault();
    setSubmittedQ(q.trim());
    setPage(1);
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className="page tickets-page">
      <div className="page-head">
        <h1>Vé hỗ trợ</h1>
        <p className="text-muted">Danh sách vé trong phạm vi của bạn.</p>
      </div>

      <form className="tickets-filters" onSubmit={applySearch}>
        <input
          className="filter-input"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          maxLength={100}
          placeholder="Tìm theo mã hoặc nội dung…"
          aria-label="Tìm kiếm"
        />
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Lọc theo trạng thái">
          <option value="">Tất cả trạng thái</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <label className="filter-check">
          <input type="checkbox" checked={assignedToMe} onChange={(e) => setAssignedToMe(e.target.checked)} />
          Vé của tôi
        </label>
        <button type="submit" className="btn-secondary">Tìm</button>
      </form>

      {error && <p className="form-error" role="alert">{error}</p>}
      {loading && <p className="text-muted">Đang tải…</p>}
      {!loading && !error && rows.length === 0 && (
        <div className="empty-state">
          <p>Không có vé nào khớp điều kiện lọc.</p>
        </div>
      )}

      {!loading && rows.length > 0 && (
        <>
          <div className="table-scroll">
            <table className="tickets-table">
              <thead>
                <tr>
                  <th>Mã</th><th>Tiêu đề</th><th>Khách hàng</th>
                  <th>Phân loại</th><th>Ưu tiên</th><th>Trạng thái</th><th>Cập nhật</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((t) => (
                  <tr key={t.id} className="tickets-row" onClick={() => navigate(`/app/tickets/${t.id}`)}>
                    <td className="code-cell">{t.ticket_code}</td>
                    <td className="subject-cell">{t.subject}</td>
                    <td>{t.requester_name}</td>
                    <td>{labelOf(CATEGORY_LABELS, t.category)}</td>
                    <td><span className={`badge badge--${(t.priority || '').toLowerCase()}`}>{labelOf(PRIORITY_LABELS, t.priority)}</span></td>
                    <td><span className={`badge badge--${(t.status || '').toLowerCase()}`}>{labelOf(STATUS_LABELS, t.status)}</span></td>
                    <td>{fmtDateTime(t.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pagination">
            <button className="btn-secondary" disabled={page <= 1} onClick={() => load(page - 1)}>‹ Trước</button>
            <span className="text-muted">Trang {page} / {totalPages} ({total} vé)</span>
            <button className="btn-secondary" disabled={page >= totalPages} onClick={() => load(page + 1)}>Sau ›</button>
          </div>
        </>
      )}
    </section>
  );
}
