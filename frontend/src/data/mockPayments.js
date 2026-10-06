export let mockPayments = [
  {
    id: 'REQ-DEMO-001',
    vendor: 'Acme Industrial Supplies',
    vendorId: 'VEND-001',
    amount: 45000,
    currency: 'INR',
    bankAccount: 'ACME-BANK-001',
    invoiceId: 'INV-2026-001',
    poId: 'PO-2026-001',
    paymentChannel: 'NEFT',
    description: 'Scenario 1: Low risk (auto-approve target)',
    status: 'AUTHORIZED',
    riskLevel: 'LOW',
    requiredApproval: 'Auto Approval',
    createdAt: '2026-10-06T10:00:00Z',
    threeWayMatch: {
      po_match: true,
      grn_match: true,
      invoice_match: true,
      overall_match: 'MATCHED'
    },
    vendorInfo: {
      approved: true,
      typicalAmount: 45000
    },
    approvalInfo: {
      required: 0,
      completed: 0,
      remaining: 0,
      status: 'Auto Approved'
    }
  },
  {
    id: 'REQ-DEMO-002',
    vendor: 'Global Tech Solutions',
    vendorId: 'VEND-002',
    amount: 150000,
    currency: 'INR',
    bankAccount: 'GLOB-BANK-002',
    invoiceId: 'INV-2026-002',
    poId: 'PO-2026-002',
    paymentChannel: 'RTGS',
    description: 'Scenario 2: Medium risk (single signature target)',
    status: 'PENDING_APPROVAL',
    riskLevel: 'MEDIUM',
    requiredApproval: '1 Signature',
    createdAt: '2026-10-06T10:15:00Z',
    threeWayMatch: {
      po_match: true,
      grn_match: true,
      invoice_match: true,
      overall_match: 'MATCHED'
    },
    vendorInfo: {
      approved: true,
      typicalAmount: 120000
    },
    approvalInfo: {
      required: 1,
      completed: 0,
      remaining: 1,
      status: 'Pending 1 Signature'
    }
  },
  {
    id: 'REQ-DEMO-003',
    vendor: 'Nexus Logistics',
    vendorId: 'VEND-003',
    amount: 85000,
    currency: 'INR',
    bankAccount: 'NEXUS-BANK-003',
    invoiceId: 'INV-2026-003',
    poId: 'PO-2026-003',
    paymentChannel: 'NEFT',
    description: 'Scenario 3: Tamper demo baseline payment',
    status: 'PENDING_APPROVAL',
    riskLevel: 'MEDIUM',
    requiredApproval: '1 Signature',
    createdAt: '2026-10-06T10:30:00Z',
    threeWayMatch: {
      po_match: true,
      grn_match: true,
      invoice_match: true,
      overall_match: 'MATCHED'
    },
    vendorInfo: {
      approved: true,
      typicalAmount: 85000
    },
    approvalInfo: {
      required: 1,
      completed: 0,
      remaining: 1,
      status: 'Pending Approval'
    }
  },
  {
    id: 'REQ-DEMO-004',
    vendor: 'Apex Shadow Corp',
    vendorId: 'VEND-004',
    amount: 350000,
    currency: 'INR',
    bankAccount: 'APEX-DIFF-999',
    invoiceId: 'INV-2026-004',
    poId: null,
    paymentChannel: 'Manual Transfer',
    description: 'Scenario 4: High risk / hold target (no PO, shadow vendor)',
    status: 'ON_HOLD',
    riskLevel: 'HIGH',
    requiredApproval: 'Analyst Review',
    createdAt: '2026-10-06T11:00:00Z',
    threeWayMatch: {
      po_match: false,
      grn_match: false,
      invoice_match: false,
      overall_match: 'MISMATCH'
    },
    vendorInfo: {
      approved: false,
      typicalAmount: 0
    },
    approvalInfo: {
      required: 1,
      completed: 0,
      remaining: 1,
      status: 'On Hold'
    }
  },
  {
    id: 'REQ001',
    vendor: 'ABC Suppliers',
    vendorId: 'V001',
    amount: 50000,
    currency: 'INR',
    bankAccount: 'XXXX1234',
    invoiceId: 'INV001',
    poId: 'PO001',
    paymentChannel: 'NEFT',
    description: 'Monthly office supplies',
    status: 'APPROVED',
    riskLevel: 'LOW',
    requiredApproval: 'Auto Approval',
    createdAt: '2026-10-01T10:30:00Z',
    threeWayMatch: {
      po_match: true,
      grn_match: true,
      invoice_match: true,
      overall_match: 'MATCHED'
    },
    vendorInfo: {
      approved: true,
      typicalAmount: 45000
    },
    approvalInfo: {
      required: 0,
      completed: 0,
      remaining: 0,
      status: 'Auto Approved'
    }
  },
  {
    id: 'REQ002',
    vendor: 'XYZ Traders',
    vendorId: 'V002',
    amount: 110000,
    currency: 'INR',
    bankAccount: 'XXXX5678',
    invoiceId: 'INV002',
    poId: 'PO002',
    paymentChannel: 'RTGS',
    description: 'Hardware upgrade',
    status: 'PENDING',
    riskLevel: 'HIGH',
    requiredApproval: '2 Signatures',
    createdAt: '2026-10-05T14:15:00Z',
    threeWayMatch: {
      po_match: true,
      grn_match: false,
      invoice_match: true,
      overall_match: 'PARTIAL MATCH'
    },
    vendorInfo: {
      approved: true,
      typicalAmount: 50000
    },
    approvalInfo: {
      required: 2,
      completed: 1,
      remaining: 1,
      status: 'Pending 1 Signature'
    }
  },
  {
    id: 'REQ003',
    vendor: 'NewTech LLC',
    vendorId: 'V003',
    amount: 150000,
    currency: 'INR',
    bankAccount: 'XXXX9999',
    invoiceId: 'INV003',
    poId: 'PO003',
    paymentChannel: 'Wire Transfer',
    description: 'Consulting services',
    status: 'HOLD',
    riskLevel: 'CRITICAL',
    requiredApproval: 'Analyst Review',
    createdAt: '2026-10-06T09:00:00Z',
    threeWayMatch: {
      po_match: false,
      grn_match: false,
      invoice_match: false,
      overall_match: 'MISMATCH'
    },
    vendorInfo: {
      approved: false,
      typicalAmount: 0
    },
    approvalInfo: {
      required: 1,
      completed: 0,
      remaining: 1,
      status: 'On Hold'
    }
  },
  {
    id: 'REQ004',
    vendor: 'Global Services',
    vendorId: 'V004',
    amount: 25000,
    currency: 'INR',
    bankAccount: 'XXXX4321',
    invoiceId: 'INV004',
    poId: 'PO004',
    paymentChannel: 'IMPS',
    description: 'Software subscription',
    status: 'PENDING',
    riskLevel: 'MEDIUM',
    requiredApproval: '1 Signature',
    createdAt: '2026-10-06T11:45:00Z',
    threeWayMatch: {
      po_match: true,
      grn_match: true,
      invoice_match: true,
      overall_match: 'MATCHED'
    },
    vendorInfo: {
      approved: true,
      typicalAmount: 24000
    },
    approvalInfo: {
      required: 1,
      completed: 0,
      remaining: 1,
      status: 'Pending Approval'
    }
  }
];

export const addMockPayment = (payment) => {
  const newPayment = {
    ...payment,
    id: `REQ${String(mockPayments.length + 1).padStart(3, '0')}`,
    status: 'PENDING',
    riskLevel: 'PENDING',
    requiredApproval: 'Pending Analysis',
    createdAt: new Date().toISOString(),
    threeWayMatch: {
      po_match: true,
      grn_match: true,
      invoice_match: true,
      overall_match: 'MATCHED' // Mock default
    },
    vendorInfo: {
      approved: true,
      typicalAmount: payment.amount
    },
    approvalInfo: {
      required: 1,
      completed: 0,
      remaining: 1,
      status: 'Pending Analysis'
    }
  };
  mockPayments = [newPayment, ...mockPayments];
  return newPayment;
};

export const getMockPayment = (id) => {
  return mockPayments.find(p => p.id === id);
};
