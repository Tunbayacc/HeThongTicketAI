import { STATUS_LABELS, labelOf } from '../lib/labels.js';

// Pure hand-drawn stacked-bar SVG (no chart dependency). Each bucket is a stack of
// five status segments; colors come from dashboard.css --seg-* vars (theme-aware).
// viewBox scales to the container width, so wide windows never overflow the page.

const H = 240;
const PAD_L = 40;   // left: y-axis count labels
const PAD_R = 10;
const PAD_T = 12;
const PAD_B = 26;   // bottom: x tick labels
const PLOT_H = H - PAD_T - PAD_B;

function bucketTotal(statuses) {
  return Object.values(statuses).reduce((acc, n) => acc + (n || 0), 0);
}

export default function DashboardTrendChart({ buckets, granularity, labels }) {
  const n = buckets.length;
  if (!n) return null;
  const plotW = Math.max(520, n * 34);
  const W = PAD_L + plotW + PAD_R;
  const slot = plotW / n;
  const barW = Math.max(5, Math.min(28, slot - 4));
  const xCenter = (i) => PAD_L + slot * i + slot / 2;

  const max = Math.max(1, ...buckets.map((b) => bucketTotal(b.statuses)));
  const yFor = (value) => PAD_T + PLOT_H * (1 - value / max);

  // Y gridlines from the max count (0 is the baseline axis).
  const gridFractions = [0.25, 0.5, 0.75, 1];
  // X ticks: every bucket up to ~14; sparse beyond so labels never collide.
  const tickEvery = n <= 14 ? 1 : Math.ceil(n / 6);
  const tickLabel = (bucket) => (granularity === 'month' ? bucket : bucket.slice(5)); // MM-DD

  const stacked = buckets.map((b) => {
    let floor = 0;
    const segs = labels
      .filter((st) => (b.statuses[st] || 0) > 0)
      .map((st) => {
        const v = b.statuses[st];
        const seg = { st, v, y: yFor(floor + v), height: yFor(floor) - yFor(floor + v) };
        floor += v;
        return seg;
      });
    return { bucket: b.bucket, segs };
  });

  return (
    <svg
      className="trend-svg"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Biểu đồ xu hướng số vé tạo mới theo trạng thái"
    >
      {gridFractions.map((f) => {
        const value = Math.round(max * f);
        const y = yFor(max * f);
        return (
          <g key={`grid-${f}`}>
            <line className="chart-grid" x1={PAD_L} y1={y} x2={PAD_L + plotW} y2={y} />
            <text className="chart-y" x={PAD_L - 6} y={y + 4} textAnchor="end">{value}</text>
          </g>
        );
      })}
      <line className="chart-axis" x1={PAD_L} y1={yFor(0)} x2={PAD_L + plotW} y2={yFor(0)} />

      {stacked.map(({ bucket, segs }, i) => (
        <g key={bucket}>
          {segs.map(({ st, v, y, height }) => (
            <rect
              key={`${bucket}-${st}`}
              className={`seg--${st.toLowerCase()}`}
              x={xCenter(i) - barW / 2}
              y={y}
              width={barW}
              height={height}
            >
              <title>{`${bucket} · ${labelOf(STATUS_LABELS, st)}: ${v}`}</title>
            </rect>
          ))}
          {i % tickEvery === 0 && (
            <text className="chart-x" x={xCenter(i)} y={H - 8} textAnchor="middle">
              {tickLabel(bucket)}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}
