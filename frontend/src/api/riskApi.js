import { mockRiskAnalysisData } from '../data/mockRiskAnalysis';

export const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

/**
 * Maps the backend /payments/{id}/score response into the format
 * expected by TrustGuard UI components.
 */
export function mapBackendScoreToUI(data) {
  const riskScore = Math.round(data.risk_score ?? 0);

  let riskLevel = 'LOW';
  if (riskScore >= 75) riskLevel = 'CRITICAL';
  else if (riskScore >= 50) riskLevel = 'HIGH';
  else if (riskScore >= 30) riskLevel = 'MEDIUM';
  else riskLevel = 'LOW';

  const reasons = (data.reasons || []).map((r) => ({
    feature: r.feature,
    label: r.description || r.feature,
    description: r.description,
    contribution: r.impact === 'high' ? 30 : r.impact === 'medium' ? 20 : 10,
    direction: 'increases_risk',
    impact: r.impact,
  }));

  const routing = {
    tier: data.routing?.routing_tier || data.routing_tier || 'AUTO_APPROVE',
    requiredSignatures: data.routing?.required_signatures ?? data.required_signatures ?? 0,
    completedSignatures: data.status === 'AUTHORIZED' ? (data.required_signatures ?? 0) : 0,
    status: data.status || 'PENDING',
  };

  const businessChecks = data.business_checks || {};
  const threeWayMatch = {
    po_match: Boolean(businessChecks.po_exists && businessChecks.po_approved),
    grn_match: Boolean(businessChecks.grn_exists && businessChecks.goods_received),
    invoice_match: Boolean(businessChecks.amount_match && !businessChecks.duplicate_invoice),
    overall_match: businessChecks.amount_match ? 'MATCHED' : 'MISMATCH',
  };

  return {
    requestId: data.request_id,
    riskScore: riskScore,
    riskLevel: riskLevel,
    fraudProbability: data.fraud_probability ?? 0,
    modelVersion: 'TrustGuard Model (Demo Provider)',
    paymentStatus: data.status || data.payment_status || 'PENDING',
    routing: routing,
    reasons: reasons,
    businessChecks: businessChecks,
    threeWayMatch: threeWayMatch,
    poId: businessChecks.details?.po_id || 'PO-2026-001',
    invoiceId: 'INV-2026-001',
    raw: data,
  };
}

/**
 * 1. Seed demo database for Acme Ltd
 * POST http://127.0.0.1:8000/seed
 */
export const seedDatabase = async () => {
  const response = await fetch(`${API_BASE}/seed`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Seed failed with status ${response.status}`);
  }
  return await response.json();
};

/**
 * 2. Score demo payment request with TrustGuard
 * POST http://127.0.0.1:8000/payments/{id}/score
 */
export const scorePayment = async (requestId = 'REQ-DEMO-001') => {
  const response = await fetch(`${API_BASE}/payments/${requestId}/score`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Scoring failed with status ${response.status}`);
  }
  const data = await response.json();
  return mapBackendScoreToUI(data);
};

/**
 * 3. Verify cryptographic SHA-256 audit hash chain
 * GET http://127.0.0.1:8000/audit-log/verify
 */
export const verifyAuditLog = async () => {
  const response = await fetch(`${API_BASE}/audit-log/verify`);
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Audit verification failed with status ${response.status}`);
  }
  return await response.json();
};

/**
 * Fetch risk analysis for a payment.
 * Calls backend live scoring endpoint, falling back to mock data if needed.
 */
export const getRiskAnalysis = async (requestId) => {
  return await scorePayment(requestId);
};
