import { startAuthentication } from '@simplewebauthn/browser';

const API_BASE = 'http://127.0.0.1:8000';

export const getPayments = async (status = null) => {
  const url = status ? `${API_BASE}/payments?status=${status}` : `${API_BASE}/payments`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch payments');
  return res.json();
};

export const getPayment = async (id) => {
  const res = await fetch(`${API_BASE}/payments/${id}`);
  if (!res.ok) throw new Error('Failed to fetch payment');
  return res.json();
};

export const getApprovers = async () => {
  const res = await fetch(`${API_BASE}/auth/webauthn/approvers`);
  if (!res.ok) throw new Error('Failed to fetch approvers');
  return res.json();
};

export const approvePaymentWithPasskey = async (requestId, approverId) => {
  // 1. Get challenge
  const challengeRes = await fetch(`${API_BASE}/payments/${requestId}/challenge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approver_id: approverId })
  });
  
  if (!challengeRes.ok) {
    const err = await challengeRes.json();
    throw new Error(err.detail || 'Failed to get challenge');
  }
  
  const challengeData = await challengeRes.json();
  
  // 2. Authenticate with browser
  let assertion;
  try {
    assertion = await startAuthentication({ optionsJSON: challengeData.webauthn_options });
  } catch (error) {
    console.error('WebAuthn error:', error);
    throw new Error('Passkey authentication failed or cancelled');
  }
  
  // 3. Submit signature
  const verifyRes = await fetch(`${API_BASE}/payments/${requestId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      approver_id: approverId,
      nonce: challengeData.nonce,
      credential: assertion,
      challenge_id: challengeData.challenge_id
    })
  });
  
  if (!verifyRes.ok) {
    const err = await verifyRes.json();
    throw new Error(err.detail || 'Failed to verify approval');
  }
  
  return verifyRes.json();
};

export const releasePayment = async (requestId, releaserId = 'finance_ops_01') => {
  const res = await fetch(`${API_BASE}/payments/${requestId}/release?releaser_id=${releaserId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to release payment');
  }
  
  return res.json();
};

export const submitAnalystDecision = async (requestId, decision, reason = 'Analyst review') => {
  const res = await fetch(`${API_BASE}/api/v1/payments/${requestId}/analyst-decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      decision,
      reason,
      analyst_id: 'analyst_01'
    })
  });
  
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to submit analyst decision');
  }
  
  return res.json();
};
