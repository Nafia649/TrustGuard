import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import PaymentBundle from '../components/security/PaymentBundle';
import ApprovalRequirements from '../components/security/ApprovalRequirements';
import PasskeyApproval from '../components/security/PasskeyApproval';
import RealKeyStatus from '../components/security/RealKeyStatus';
import SecurityDetails from '../components/security/SecurityDetails';
import Button from '../components/common/Button';
import Card from '../components/common/Card';
import { formatINR } from '../utils/formatters';
import { ArrowLeft, CheckCircle, XCircle } from 'lucide-react';
import { getPayment, getApprovers, approvePaymentWithPasskey } from '../api/paymentApi';

export default function PaymentApproval() {
  const { id } = useParams();
  const navigate = useNavigate();
  
  const [payment, setPayment] = useState(null);
  const [approversList, setApproversList] = useState([]);
  const [selectedApproverId, setSelectedApproverId] = useState('');
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [passkeyStatus, setPasskeyStatus] = useState('ready'); // ready, authenticating, success, error
  const [authError, setAuthError] = useState(null);
  const [realkeyResult, setRealkeyResult] = useState(null); // null, 'success', 'failure'
  const [simulateFailure, setSimulateFailure] = useState(false);

  const loadData = async () => {
    try {
      setLoading(true);
      const [payData, apprs] = await Promise.all([
        getPayment(id),
        getApprovers()
      ]);
      setPayment(payData);
      setApproversList(apprs);
      if (apprs.length > 0) {
        setSelectedApproverId(apprs[0].approver_id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [id]);

  if (loading) {
    return <div className="text-center py-12 text-text-muted">Loading payment details...</div>;
  }

  if (error || !payment) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-bold text-danger">Error Loading Approval</h2>
        <p className="text-text-muted mt-2">{error}</p>
        <Link to="/approval" className="text-primary mt-4 inline-block hover:underline">← Back to Approvals</Link>
      </div>
    );
  }

  const isHold = payment.routing_tier === 'HOLD';
  const isAuto = payment.routing_tier === 'AUTO_APPROVE';
  const isAuth = payment.status === 'AUTHORIZED' || payment.status === 'RELEASED';
  
  const disabled = isHold || isAuto || isAuth;
  const disabledReason = isAuth 
    ? "Payment has already been authorized."
    : isHold 
    ? "Payment is currently on hold due to risk." 
    : "This payment was auto-approved.";

  const handlePasskeyStart = async () => {
    setPasskeyStatus('authenticating');
    setAuthError(null);
    try {
      if (simulateFailure) {
        throw new Error("Simulated tamper detection or failure");
      }
      
      const result = await approvePaymentWithPasskey(payment.request_id, selectedApproverId);
      setPasskeyStatus('success');
      setRealkeyResult('success');
      await loadData(); // refresh
    } catch (err) {
      console.error(err);
      setAuthError(err.message);
      setPasskeyStatus('ready');
      setRealkeyResult('failure');
    }
  };

  // Map to the format expected by the child components
  const riskLevel = payment.risk_score >= 90 ? 'CRITICAL' : payment.risk_score >= 50 ? 'HIGH' : 'LOW';
  
  const mappedApproval = {
    vendor: payment.vendor_id,
    vendorId: payment.vendor_id,
    amount: payment.amount,
    currency: payment.currency,
    bankAccount: payment.bank_account,
    invoiceId: payment.invoice_id,
    poId: payment.po_id || 'None',
    riskScore: Math.round(payment.risk_score || 0),
    riskLevel: riskLevel,
    routingTier: payment.routing_tier || 'AUTO_APPROVE',
    requiredSignatures: payment.required_signatures || 0,
    completedSignatures: payment.status === 'AUTHORIZED' || payment.status === 'RELEASED' ? (payment.required_signatures || 1) : 0,
    approvers: payment.status === 'AUTHORIZED' ? [{ name: "Verified Approver" }] : [],
    nonce: "Generated at challenge step",
    expiry: "Generated at challenge step",
    policyVersion: "1.0",
    mockFingerprint: "REALKEY ensures end-to-end immutability"
  };

  if (realkeyResult === 'success') {
    const selectedApprObj = approversList.find(a => a.approver_id === selectedApproverId);
    return (
      <div className="max-w-2xl mx-auto mt-8">
        <Card className="border-success/40 bg-success/5 p-8 text-center">
          <CheckCircle className="w-16 h-16 text-success mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-success mb-6 tracking-widest">PAYMENT AUTHORIZED</h2>
          
          <div className="bg-navy-bg border border-navy-border rounded-lg p-6 text-left space-y-4 max-w-md mx-auto mb-8">
            <div className="flex justify-between border-b border-navy-border pb-2">
              <span className="text-text-muted">Payment:</span>
              <span className="font-bold text-text-main">{formatINR(payment.amount)}</span>
            </div>
            <div className="flex justify-between border-b border-navy-border pb-2">
              <span className="text-text-muted">Vendor:</span>
              <span className="font-medium text-text-main">{payment.vendor_id}</span>
            </div>
            <div className="flex justify-between border-b border-navy-border pb-2">
              <span className="text-text-muted">Authorization:</span>
              <span className="font-medium text-success flex items-center"><CheckCircle className="w-3.5 h-3.5 mr-1" /> REALKEY VERIFIED</span>
            </div>
            <div className="flex justify-between border-b border-navy-border pb-2">
              <span className="text-text-muted">Approval:</span>
              <span className="font-medium text-text-main">{selectedApprObj?.name || selectedApproverId}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Timestamp:</span>
              <span className="font-medium text-text-main">{new Date().toLocaleString()}</span>
            </div>
          </div>
          
          <div className="flex flex-col sm:flex-row justify-center gap-4">
            <Button onClick={() => navigate(`/payments/${id}`)}>View Payment</Button>
            <Button variant="secondary" onClick={() => navigate('/audit')}>View Audit Trail</Button>
          </div>
        </Card>
      </div>
    );
  }

  if (realkeyResult === 'failure') {
    return (
      <div className="max-w-2xl mx-auto mt-8">
        <Card className="border-danger/40 bg-danger/5 p-8 text-center">
          <XCircle className="w-16 h-16 text-danger mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-danger mb-2 tracking-widest">PAYMENT AUTHORIZATION FAILED</h2>
          <p className="text-text-muted mb-6">Payment verification failed.</p>
          
          <div className="bg-navy-bg border border-danger/30 rounded-lg p-4 text-left max-w-md mx-auto mb-8 text-sm text-danger/90">
            <p className="font-bold mb-2">Backend Response:</p>
            <p className="font-mono">{authError}</p>
          </div>
          
          <Button onClick={() => {
            setPasskeyStatus('ready');
            setRealkeyResult(null);
            setAuthError(null);
            setSimulateFailure(false);
          }}>Try Again</Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex items-center space-x-4 mb-2">
        <Link to="/approval" className="text-text-muted hover:text-text-main">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-text-main">Approve Payment</h1>
          <p className="text-sm text-text-muted mt-1">Review the exact payment details before authorizing.</p>
        </div>
      </div>
      
      {!disabled && (
        <div className="flex justify-between items-center bg-navy-bg p-4 rounded-lg border border-navy-border">
          <div className="text-sm text-text-muted">Select active approver (Demo feature):</div>
          <select 
            value={selectedApproverId}
            onChange={(e) => setSelectedApproverId(e.target.value)}
            className="bg-navy-surface border border-navy-border rounded px-3 py-1.5 text-text-main focus:outline-none focus:border-primary"
          >
            {approversList.map(a => (
              <option key={a.approver_id} value={a.approver_id}>
                {a.name} ({a.role})
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Hidden toggle for demoing failure */}
      <div className="flex justify-end">
        <label className="flex items-center space-x-2 text-xs text-text-muted cursor-pointer">
          <input 
            type="checkbox" 
            checked={simulateFailure} 
            onChange={(e) => setSimulateFailure(e.target.checked)} 
            className="rounded border-navy-border bg-navy-bg text-primary focus:ring-primary"
          />
          <span>Simulate Tampering / Failure</span>
        </label>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <PaymentBundle approval={mappedApproval} />
          
          <PasskeyApproval 
            onApprove={handlePasskeyStart} 
            disabled={disabled} 
            disabledReason={disabledReason}
            status={passkeyStatus}
          />
        </div>
        
        <div className="lg:col-span-1 space-y-6">
          <ApprovalRequirements approval={mappedApproval} />
          <SecurityDetails />
        </div>
      </div>
    </div>
  );
}
