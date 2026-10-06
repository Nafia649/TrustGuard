const API_BASE = 'http://127.0.0.1:8000';

export const getPolicy = async () => {
  const res = await fetch(`${API_BASE}/api/v1/policy`);
  if (!res.ok) throw new Error('Failed to fetch active policy');
  return res.json();
};

export const getPolicyHistory = async () => {
  const res = await fetch(`${API_BASE}/api/v1/policy/history`);
  if (!res.ok) throw new Error('Failed to fetch policy history');
  return res.json();
};

export const updatePolicy = async (policyConfig, changedBy, changeReason) => {
  const res = await fetch(`${API_BASE}/api/v1/policy`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      policy: policyConfig,
      changed_by: changedBy,
      change_reason: changeReason
    })
  });
  
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to update policy');
  }
  return res.json();
};
