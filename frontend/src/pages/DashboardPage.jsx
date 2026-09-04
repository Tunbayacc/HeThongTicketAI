import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client.js';
import { STATUS_LABELS, labelOf } from '../lib/labels.js';
import DashboardTrendChart from '../components/DashboardTrendChart.jsx';
import '../styles/dashboard.css';

// Backend buckets carry every status 0-filled, so the chart/legend just read the
// five enum keys in a fixed order — the page never invents a bucket or a status.
const STATUS_ORDER = ['OPEN', 'IN_PROGRESS', 'PENDING', 'RESOLVED', 'CLOSED'];

const PRESETS = [
  { days: 7, label: '7 ngày qua' },
  { days: 30, label: '30 ngày qua' },
  { days: 90, label: '90 ngày qua' },
  { days: 180, label: '6 tháng qua' },
  { days: 365, label: '1 năm qua' },
];

const pad = (n) => String(n).padStart(2, '0');
const fmtLocal = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

function rangeFor(days) {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - (days - 1));
  return { from: fmtLocal(from), to: fmtLocal(to) };
}

let loadSeq = 0;

function fmtDuration(totalSeconds) {
  if (totalSeconds < 60) return `${totalSeconds} giây`;
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  if (m < 60) return s ? `${m} phút ${s} giây` : `${m} phút`;
  const h = Math.floor(m / 60);
  const mm = m % 60;
  return mm ? `${h} giờ ${mm} phút` : `${h} giờ`;
}

const fmtCount = (n) => (n ?? 0).toLocaleString('vi-VN');

export default function DashboardPage() {
  const navigate = useNavigate();
  const [range, setRange] = useState(() => rangeFor(30));
  const [preset, setPreset] = useState(30);
  const [summary, setSummary] = useState(null);
  const [trends, setTrends] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function load() {
    const seq = ++loadSeq;
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams({ from: range.from, to: range.to }).toString();
      const [s, t] = await Promise.all([
        api.get(`/api/dashboard/summary?${qs}`),
        api.get(`/api/dashboard/trends?${qs}`),
      ]);
      if (seq !== loadSeq) return;
      setSummary(s);
      setTrends(t);
    } catch (err) {
      if (seq !== loadSeq) return;
      setError(err.message || 'Không thể tải dữ liệu bảng điều khiển.');
      setSummary(null);
      setTrends(null);
    } finally {
      if (seq === loadSeq) setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range.from, range.to]);

  function applyPreset(days) {
    setPreset(days);
    setRange(rangeFor(days));
  }

  function onDate(field, value) {
    setPreset(null);
    setRange((prev) => ({ ...prev, [field]: value }));
  }

  function drillDown(statusFilter) {
    const params = new URLSearchParams();
    if (statusFilter) params.set('status', statusFilter);
    navigate(`/app/tickets?${params.toString()}`);
  }

  const kpi = summary?.kpi;
  const byStatus = kpi?.by_status ?? {};
  const sla = summary?.sla;
  const empty = !loading && !error && summary && kpi.total === 0;

  const cards = summary && [
    { label: 'Tổng số vé', value: kpi.total, className: 'kpi-total', filter: null },
    { label: 'Vé đang mở', value: byStatus.OPEN, filter: 'OPEN' },
    { label: 'Đang xử lý', value: byStatus.IN_PROGRESS, filter: 'IN_PROGRESS' },
    { label: 'Chờ phản hồi', value: byStatus.PENDING, filter: 'PENDING' },
    { label: 'Đã giải quyết / Đóng', value: (byStatus.RESOLVED ?? 0) + (byStatus.CLOSED ?? 0), filter: null },
    { label: 'Quá hạn SLA', value: sla.overdue, className: sla.overdue > 0 ? 'kpi-over' : '', filter: null },
  ];

  const avgCells = summary && [
    { label: 'Thời gian phản hồi đầu tiên (trung bình)', seconds: summary.avg_first_response_seconds },
    { label: 'Thời gian giải quyết hoàn tất (trung bình)', seconds: summary.avg_resolution_seconds },
  ];

  const granLabel = trends?.range?.granularity === 'month' ? 'tháng' : 'ngày';

  return (
    <section className="page dashboard-page">
      <div className="page-head">
        <div>
          <h1>Bảng điều khiển & Báo cáo</h1>
          <p className="text-muted text-sm">Thống kê chỉ số hoạt động, cam kết SLA và xu hướng vé theo phạm vi quyền hạn</p>
        </div>
      </div>

      <div className="dash-toolbar" role="group" aria-label="Bộ lọc khoảng thời gian">
        <div className="dash-presets">
          {PRESETS.map((p) => (
            <button
              key={p.days}
              type="button"
              className={preset === p.days ? 'preset active' : 'preset'}
              onClick={() => applyPreset(p.days)}
            >
              {p.label}
            </button>
          ))}
        </div>
        <label className="dash-date">
          <span>Từ ngày:</span>
          <input type="date" value={range.from} onChange={(e) => onDate('from', e.target.value)} />
        </label>
        <label className="dash-date">
          <span>Đến ngày:</span>
          <input type="date" value={range.to} onChange={(e) => onDate('to', e.target.value)} />
        </label>
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}
      {loading && <p className="text-muted state-loading">Đang tải số liệu thống kê…</p>}

      {empty && (
        <div className="empty-state">
          <p>Chưa có dữ liệu vé nào phát sinh trong khoảng thời gian đã chọn.</p>
        </div>
      )}

      {summary && !empty && (
        <>
          <div className="dash-section">
            <h2 className="dash-section-title">Chỉ số tổng quan vé</h2>
            <div className="kpi-row">
              {cards.map((c) => (
                <div
                  key={c.label}
                  className={`kpi-card ${c.className || ''} ${c.filter ? 'kpi-clickable' : ''}`}
                  onClick={c.filter ? () => drillDown(c.filter) : undefined}
                  role={c.filter ? 'button' : undefined}
                  tabIndex={c.filter ? 0 : undefined}
                  onKeyDown={c.filter ? (e) => { if (e.key === 'Enter') drillDown(c.filter); } : undefined}
                  title={c.filter ? `Bấm để lọc danh sách vé: ${c.label}` : undefined}
                >
                  <span className="kpi-value">{fmtCount(c.value)}</span>
                  <span className="kpi-label">{c.label}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="dash-section">
            <h2 className="dash-section-title">Cam kết chất lượng dịch vụ (SLA)</h2>
            <div className="sla-strip" role="group" aria-label="Chỉ số SLA">
              <span className="sla-chip sla-chip--ok">✓ Trong hạn cam kết: {sla.on_time}</span>
              <span className="sla-chip sla-chip--warn">⏳ Sắp quá hạn: {sla.due_soon}</span>
              <span className="sla-chip sla-chip--over">⚠ Đã quá hạn: {sla.overdue}</span>
              <span className="sla-muted">Đang giám sát {sla.tracked} vé đang mở áp dụng chính sách SLA</span>
            </div>
          </div>

          <div className="dash-section">
            <h2 className="dash-section-title">Hiệu suất xử lý trung bình</h2>
            <div className="avg-row">
              {avgCells.map((cell) => (
                <div key={cell.label} className="avg-cell">
                  <span className="avg-label">{cell.label}</span>
                  <span className="avg-value">
                    {cell.seconds === null || cell.seconds === undefined
                      ? 'Chưa có dữ liệu tính toán'
                      : `~${fmtDuration(cell.seconds)}`}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {summary && trends && !empty && (
        <div className="dash-section">
          <div className="chart-card">
            <h2>Xu hướng vé tạo mới theo thời gian</h2>
            <p className="chart-sub">
              Phân bổ số lượng vé tạo mới theo trạng thái hiện tại, tính theo từng {granLabel} · Từ {summary.range.from} đến {summary.range.to}
            </p>
            <div className="trend-legend" aria-hidden="true">
              {STATUS_ORDER.map((st) => (
                <span key={st} className="trend-legend-item">
                  <span className={`legend-dot seg--${st.toLowerCase()}`} />
                  {labelOf(STATUS_LABELS, st)}
                </span>
              ))}
            </div>
            <div className="trend-scroll">
              <DashboardTrendChart
                buckets={trends.buckets}
                granularity={trends.range.granularity}
                labels={STATUS_ORDER}
              />
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
