import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import {
  CATEGORY_LABELS, PRIORITY_LABELS, STATUS_LABELS, fmtDateTime, labelOf,
} from '../lib/labels.js';
import '../styles/tickets.css';

const PAGE_SIZE = 10;

export default function TicketsListPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [rows, setRows] = useState([]);          // TicketListItem[]
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Initialize status from URL params (for dashboard drill-down)
  const [status, setStatus] = useState(() => searchParams.get('status') || '');
  const [priority, setPriority] = useState('');
  const [q, setQ] = useState('');
  const [assignedToMe, setAssignedToMe] = useState(false);
  const [submittedQ, setSubmittedQ] = useState('');

  const { user } = useAuth();
  const canFilterTeam = user?.role === 'MANAGER' || user?.role === 'ADMIN';
  const [teams, setTeams] = useState([]);
  const [teamFilter, setTeamFilter] = useState('');

  async function load(nextPage = page, filters = {}) {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        page: String(nextPage),
        page_size: String(PAGE_SIZE),
      });
      const st = filters.status ?? status;
      const pri = filters.priority ?? priority;
      const query = filters.q ?? submittedQ;
      const mine = filters.assignedToMe ?? assignedToMe;
      if (st) params.set('status', st);
      if (pri) params.set('priority', pri);
      if (query) params.set('q', query);
      if (mine) params.set('assigned_to_me', 'true');
      const tf = filters.teamFilter ?? teamFilter;
      if (tf) params.set('team_id', tf);
      const body = await api.get(`/api/tickets?${params.toString()}`);
      setRows(body.items);
      setTotal(body.total);
      setPage(nextPage);
    } catch (err) {
      setError(err.message || 'Không thể tải danh sách vé hỗ trợ.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(1, { status, priority, q: submittedQ, assignedToMe, teamFilter });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, priority, submittedQ, assignedToMe, teamFilter]);

  useEffect(() => {
    if (!canFilterTeam) return;
    api.get('/api/teams').then(setTeams).catch(() => setTeams([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canFilterTeam]);

  function applySearch(e) {
    e.preventDefault();
    setSubmittedQ(q.trim());
    setPage(1);
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className="page tickets-page">
      <div className="page-head">
        <div>
          <div className="page-title-row">
            <h1 className="page-title">Danh sách vé hỗ trợ</h1>
            <span className="page-badge">Support Inbox</span>
          </div>
          <p className="page-subtitle">Theo dõi, phân công và xử lý các yêu cầu hỗ trợ khách hàng theo cam kết chất lượng dịch vụ</p>
        </div>
      </div>

      <form className="tickets-filters" onSubmit={applySearch}>
        <div className="filter-search-wrap">
          <input
            className="filter-input"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            maxLength={100}
            placeholder="Tìm theo mã vé, tiêu đề hoặc nội dung…"
            aria-label="Tìm kiếm vé"
          />
          {q && (
            <button
              type="button"
              className="btn-ghost btn-sm"
              onClick={() => { setQ(''); setSubmittedQ(''); setPage(1); }}
              title="Xóa tìm kiếm"
              aria-label="Xóa tìm kiếm"
            >
              ✕
            </button>
          )}
          <button type="submit" className="btn-secondary btn-sm filter-search-btn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <span>Tìm kiếm</span>
          </button>
        </div>

        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Lọc theo trạng thái">
          <option value="">Tất cả trạng thái</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <select value={priority} onChange={(e) => setPriority(e.target.value)} aria-label="Lọc theo mức ưu tiên">
          <option value="">Tất cả mức ưu tiên</option>
          {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        {canFilterTeam && (
          <select value={teamFilter} onChange={(e) => setTeamFilter(e.target.value)} aria-label="Lọc theo nhóm hỗ trợ">
            <option value="">Tất cả nhóm hỗ trợ</option>
            {teams.map((t) => <option key={t.id} value={String(t.id)}>{t.name}</option>)}
          </select>
        )}
        <label className="filter-check">
          <input type="checkbox" checked={assignedToMe} onChange={(e) => setAssignedToMe(e.target.checked)} />
          Chỉ vé tôi phụ trách
        </label>
      </form>

      {error && <p className="form-error" role="alert">{error}</p>}
      {loading && <p className="text-muted state-loading">Đang tải danh sách vé…</p>}
      {!loading && !error && rows.length === 0 && (
        <div className="empty-state">
          <p>Không tìm thấy vé hỗ trợ nào phù hợp với bộ lọc hiện tại.</p>
        </div>
      )}

      {!loading && rows.length > 0 && (
        <div className="table-wrap">
          <div className="table-scroll">
            <table className="tickets-table">
              <thead>
                <tr>
                  <th>MÃ VÉ</th>
                  <th>TIÊU ĐỀ YÊU CẦU</th>
                  <th>KHÁCH HÀNG</th>
                  <th>PHỤ TRÁCH</th>
                  <th>PHÂN LOẠI</th>
                  <th>MỨC ĐỘ</th>
                  <th>TRẠNG THÁI</th>
                  <th>CẬP NHẬT</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((t) => (
                  <tr key={t.id} className="tickets-row" onClick={() => navigate(`/app/tickets/${t.id}`)}>
                    <td className="code-cell">
                      <span className="code-badge">{t.ticket_code}</span>
                    </td>
                    <td className="subject-cell">{t.subject}</td>
                    <td className="text-sm">{t.requester_name}</td>
                    <td className="assign-cell">
                      <span className="assign-team">{t.team_name || '—'}</span>
                      {t.team_name && <br />}
                      <span className="assign-person">
                        {t.assignee_name || (t.team_name ? 'Chưa phân công' : '')}
                      </span>
                      {t.needs_reassignment && <span className="badge badge--pending" style={{ marginLeft: 4 }}>Cần gán lại</span>}
                    </td>
                    <td><span className="text-sm">{labelOf(CATEGORY_LABELS, t.category)}</span></td>
                    <td><span className={`badge badge--${(t.priority || '').toLowerCase()}`}>{labelOf(PRIORITY_LABELS, t.priority)}</span></td>
                    <td><span className={`badge badge--${(t.status || '').toLowerCase()}`}>{labelOf(STATUS_LABELS, t.status)}</span></td>
                    <td className="text-sm text-muted">{fmtDateTime(t.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pagination">
            <span className="text-muted">Tổng cộng: {total} vé · Trang {page} / {totalPages}</span>
            <div className="pagination-controls">
              <button className="btn-secondary btn-sm" disabled={page <= 1} onClick={() => load(page - 1)}>‹ Trang trước</button>
              <button className="btn-secondary btn-sm" disabled={page >= totalPages} onClick={() => load(page + 1)}>Trang sau ›</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
