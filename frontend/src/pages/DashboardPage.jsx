import { useEffect, useState } from 'react';
import { api } from '../api/client.js';
import { STATUS_LABELS, labelOf } from '../lib/labels.js';
import DashboardTrendChart from '../components/DashboardTrendChart.jsx';
import '../styles/dashboard.css';

// Backend buckets carry every status 0-filled, so the chart/legend just read the
// five enum keys in a fixed order — the page never invents a bucket or a status.
const STATUS_ORDER = ['OPEN', 'IN_PROGRESS', 'PENDING', 'RESOLVED', 'CLOSED'];

const PRESETS = [
  { days: 7, label: '7 ngày' },
  { days: 30, label: '30 ngày' },
  { days: 90, label: '90 ngày' },
  { days: 180, label: '180 ngày' },
  { days: 365, label: '365 ngày' },
];

const pad = (n) => String(n).padStart(2, '0');
// Local (browser) calendar date, never d.toISOString().slice(0, 10): toISOString
// shifts to UTC and can flip the day for timezones ahead of UTC.
const fmtLocal = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

function rangeFor(days) {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - (days - 1)); // inclusive: today..today-(N-1)
  return { from: fmtLocal(from), to: fmtLocal(to) };
}

// Module-level sequence guard: a fast preset switch must never let a stale
// response overwrite a newer one (each load bumps it; stale awaits bail out).
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
      // Both fetches fire together and land in ONE state update (atomic pair).
      const [s, t] = await Promise.all([
        api.get(`/api/dashboard/summary?${qs}`),
        api.get(`/api/dashboard/trends?${qs}`),
      ]);
      if (seq !== loadSeq) return;
      setSummary(s);
      setTrends(t);
    } catch (err) {
      if (seq !== loadSeq) return; // superseded — ignore
      // A backend 422 (e.g. inverted range) carries a Vietnamese message to show inline.
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

  const kpi = summary?.kpi;
  const byStatus = kpi?.by_status ?? {};
  const sla = summary?.sla;
  const empty = !loading && !error && summary && kpi.total === 0;

  const cards = summary && [
    { label: 'Tổng', value: kpi.total, className: 'kpi-total' },
    { label: labelOf(STATUS_LABELS, 'OPEN'), value: byStatus.OPEN },
    { label: labelOf(STATUS_LABELS, 'IN_PROGRESS'), value: byStatus.IN_PROGRESS },
    { label: labelOf(STATUS_LABELS, 'PENDING'), value: byStatus.PENDING },
    { label: 'Đã giải quyết/Đóng', value: (byStatus.RESOLVED ?? 0) + (byStatus.CLOSED ?? 0) },
    { label: 'Quá hạn SLA', value: sla.overdue, className: sla.overdue > 0 ? 'kpi-over' : 'kpi-total' },
  ];

  const avgCells = summary && [
    { label: 'Phản hồi đầu tiên', seconds: summary.avg_first_response_seconds },
    { label: 'Thời gian giải quyết', seconds: summary.avg_resolution_seconds },
  ];

  const granLabel = trends?.range?.granularity === 'month' ? 'tháng' : 'ngày';

  return (
    <section className="page dashboard-page">
      <div className="page-head">
        <h1>Bảng điều khiển</h1>
        <p className="text-muted">Thống kê vé trong phạm vi của bạn.</p>
      </div>

      <div className="dash-toolbar" role="group" aria-label="Khoảng thời gian">
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
          Từ
          <input type="date" value={range.from} onChange={(e) => onDate('from', e.target.value)} />
        </label>
        <label className="dash-date">
          Đến
          <input type="date" value={range.to} onChange={(e) => onDate('to', e.target.value)} />
        </label>
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}
      {loading && <p className="text-muted">Đang tải…</p>}

      {empty && (
        <div className="empty-state">
          <p>Chưa có dữ liệu trong khoảng thời gian này.</p>
        </div>
      )}

      {summary && !empty && (
        <div className="kpi-row">
          {cards.map((c) => (
            <div key={c.label} className={`kpi-card ${c.className || ''}`}>
              <span className="kpi-value">{fmtCount(c.value)}</span>
              <span className="kpi-label">{c.label}</span>
            </div>
          ))}
        </div>
      )}

      {summary && !empty && (
        <div className="sla-strip" role="group" aria-label="Trạng thái SLA">
          <span className="sla-chip sla-chip--ok">Trong hạn: {sla.on_time}</span>
          <span className="sla-chip sla-chip--warn">Sắp quá hạn: {sla.due_soon}</span>
          <span className="sla-chip sla-chip--over">Quá hạn: {sla.overdue}</span>
          <span className="sla-muted">Theo dõi {sla.tracked} vé đang mở có SLA</span>
        </div>
      )}

      {summary && !empty && (
        <div className="avg-row">
          {avgCells.map((cell) => (
            <div key={cell.label} className="avg-cell">
              <span className="avg-label">{cell.label}</span>
              <span className="avg-value">
                {cell.seconds === null || cell.seconds === undefined
                  ? 'Chưa có dữ liệu'
                  : `Trung bình ~${fmtDuration(cell.seconds)}`}
              </span>
            </div>
          ))}
        </div>
      )}

      {summary && trends && !empty && (
        <div className="chart-card">
          <h2>Xu hướng vé tạo mới</h2>
          <p className="chart-sub">
            Số lượng theo trạng thái hiện tại, theo từng {granLabel} · Khoảng{' '}
            {summary.range.from} → {summary.range.to}
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
      )}
    </section>
  );
}
