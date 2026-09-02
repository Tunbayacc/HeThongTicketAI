// S2 UI copy: identifiers stay English (enum values), display always Vietnamese
// (Global Constraint). Keep maps in sync with backend app/models/enums.py.
export const STATUS_LABELS = {
  OPEN: 'Mở',
  IN_PROGRESS: 'Đang xử lý',
  PENDING: 'Chờ bổ sung thông tin',
  RESOLVED: 'Đã giải quyết',
  CLOSED: 'Đã đóng',
};

export const PRIORITY_LABELS = {
  LOW: 'Thấp',
  MEDIUM: 'Trung bình',
  HIGH: 'Cao',
  URGENT: 'Khẩn cấp',
};

export const CATEGORY_LABELS = {
  TECHNICAL: 'Kỹ thuật',
  ACCOUNT: 'Tài khoản',
  BILLING: 'Thanh toán',
  GENERAL: 'Chung',
  OTHER: 'Khác',
};

export const VISIBILITY_LABELS = {
  PUBLIC: 'Công khai',
  INTERNAL: 'Nội bộ',
};

export function labelOf(map, value) {
  return (value && map[value]) || value || '—';
}

// UTC ISO 8601 from the API -> local Vietnamese display (Global Constraint).
export function fmtDateTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('vi-VN');
}

export function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('vi-VN');
}
