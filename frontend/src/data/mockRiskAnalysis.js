export const mockRiskAnalysisData = {
  REQ001: {
    requestId: "REQ001",
    fraudProbability: 0.08,
    riskScore: 8,
    riskLevel: "LOW",
    modelVersion: "trustguard-xgb-v1",
    reasons: [
      { feature: "vendor_approved", label: "Approved vendor", contribution: -12, direction: "reduces_risk" },
      { feature: "amount_vs_vendor_average", label: "Amount is close to vendor's usual amount", contribution: -8, direction: "reduces_risk" }
    ],
    routing: {
      tier: "AUTO_APPROVE",
      requiredSignatures: 0,
      completedSignatures: 0
    }
  },
  REQ002: {
    requestId: "REQ002",
    fraudProbability: 0.55,
    riskScore: 55,
    riskLevel: "MEDIUM",
    modelVersion: "trustguard-xgb-v1",
    reasons: [
      { feature: "amount_vs_vendor_average", label: "Amount is higher than vendor's usual amount", contribution: 15, direction: "increases_risk" },
      { feature: "unusual_time", label: "Unusual request time", contribution: 8, direction: "increases_risk" },
      { feature: "vendor_approved", label: "Approved vendor", contribution: -10, direction: "reduces_risk" }
    ],
    routing: {
      tier: "ONE_SIGNATURE",
      requiredSignatures: 1,
      completedSignatures: 0
    }
  },
  REQ003: {
    requestId: "REQ003",
    fraudProbability: 0.82,
    riskScore: 82,
    riskLevel: "HIGH",
    modelVersion: "trustguard-xgb-v1",
    reasons: [
      { feature: "amount_vs_vendor_average", label: "Amount significantly higher than usual", contribution: 22, direction: "increases_risk" },
      { feature: "bank_account_changed", label: "Bank account changed recently", contribution: 18, direction: "increases_risk" },
      { feature: "unusual_time", label: "Unusual transaction time", contribution: 11, direction: "increases_risk" }
    ],
    routing: {
      tier: "TWO_SIGNATURES",
      requiredSignatures: 2,
      completedSignatures: 1
    }
  },
  REQ004: {
    requestId: "REQ004",
    fraudProbability: 0.96,
    riskScore: 96,
    riskLevel: "CRITICAL",
    modelVersion: "trustguard-xgb-v1",
    reasons: [
      { feature: "new_vendor", label: "New, unverified vendor", contribution: 35, direction: "increases_risk" },
      { feature: "amount_large", label: "Exceptionally large transaction amount", contribution: 25, direction: "increases_risk" },
      { feature: "bank_account_flagged", label: "Bank account flagged as suspicious", contribution: 30, direction: "increases_risk" }
    ],
    routing: {
      tier: "HOLD",
      requiredSignatures: 1,
      completedSignatures: 0
    }
  }
};
