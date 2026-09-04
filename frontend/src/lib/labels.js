// S2 UI copy: identifiers stay English (enum values), display always Vietnamese
// (Global Constraint). Keep maps in sync with backend app/models/enums.py.

export const STATUS_LABELS = {
  OPEN: 'Mở',
  IN_PROGRESS: 'Đang xử lý',
  PENDING: 'Chờ phản hồi',
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

export const ROLE_LABELS = {
  AGENT: 'Nhân viên hỗ trợ',
  MANAGER: 'Quản lý nhóm',
  ADMIN: 'Quản trị viên',
};

export const ROLE_SHORT_LABELS = {
  AGENT: 'Nhân viên',
  MANAGER: 'Quản lý',
  ADMIN: 'Quản trị viên',
};

export const TEAM_ROLE_LABELS = {
  MEMBER: 'Thành viên',
  MANAGER: 'Trưởng nhóm',
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

// S4 AI copy: keys equal AiResultType / AiStatus enum values (English keys,
// Vietnamese display — Global Constraint; see backend app/models/enums.py).
export const AI_TYPE_LABELS = {
  CLASSIFICATION: 'Phân loại',
  SUMMARY: 'Tóm tắt',
  DRAFT_REPLY: 'Nháp trả lời',
};

export const AI_STATUS_LABELS = {
  PENDING_REVIEW: 'Chờ duyệt',
  APPROVED: 'Đã duyệt',
  EDITED: 'Đã chỉnh sửa',
  REJECTED: 'Đã từ chối',
  FAILED: 'Lỗi',
};
