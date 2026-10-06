import { mockRiskAnalysisData } from '../data/mockRiskAnalysis';

export const getRiskAnalysis = async (requestId) => {
  // Simulate network delay
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      const data = mockRiskAnalysisData[requestId];
      if (data) {
        resolve(data);
      } else {
        // Fallback for newly created payments
        resolve({
          requestId,
          fraudProbability: 0.15,
          riskScore: 15,
          riskLevel: "LOW",
          modelVersion: "trustguard-xgb-v1",
          reasons: [
            { feature: "vendor_approved", label: "Approved vendor", contribution: -10, direction: "reduces_risk" }
          ],
          routing: {
            tier: "AUTO_APPROVE",
            requiredSignatures: 0,
            completedSignatures: 0
          }
        });
      }
    }, 500);
  });
};
