const API_BASE = 'http://127.0.0.1:8000';

export const getAuditLogs = async (params = {}) => {
  const q = new URLSearchParams(params).toString();
  const url = `${API_BASE}/api/v1/audit-log${q ? '?' + q : ''}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch audit logs');
  return res.json();
};

export const verifyAuditChain = async () => {
  const res = await fetch(`${API_BASE}/api/v1/audit-log/verify`);
  if (!res.ok) throw new Error('Failed to verify audit chain');
  return res.json();
};
