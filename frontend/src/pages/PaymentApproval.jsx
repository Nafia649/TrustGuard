import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { getMockApproval } from '../data/mockApprovalData';
import PaymentBundle from '../components/security/PaymentBundle';
import ApprovalRequirements from '../components/security/ApprovalRequirements';
import PasskeyApproval from '../components/security/PasskeyApproval';
import RealKeyStatus from '../components/security/RealKeyStatus';
import SecurityDetails from '../components/security/SecurityDetails';
import Button from '../components/common/Button';
import Card from '../components/common/Card';
import { formatINR } from '../utils/formatters';
import { ArrowLeft, CheckCircle, XCircle } from 'lucide-react';

export default function PaymentApproval() {
  const { id } = useParams();
  const navigate = useNavigate();
  const approval = getMockApproval(id);
  
  const [passkeyDone, setPasskeyDone] = useState(false);
  const [realkeyResult, setRealkeyResult] = useState(null); // null, 'success', 'failure'
  
  // For demo purposes, we can simulate a failure if the URL has ?fail=true, 
  // or we can add a small hidden button. Let's just simulate success for now, 
  // and provide a toggle for demoing failure.
  const [simulateFailure, setSimulateFailure] = useState(false);

  if (!approval) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-bold text-text-main">Approval Not Found</h2>
        <Link to={`/payments/${id}`} className="text-primary mt-4 inline-block hover:underline">← Back to Payment</Link>
      </div>
    );
  }

  const isHold = approval.routingTier === 'HOLD';
  const isAuto = approval.routingTier === 'AUTO_APPROVE';
  const disabled = isHold || isAuto;
  const disabledReason = isHold 
    ? "Payment is currently on hold." 
    : "This payment was auto-approved.";

  const handlePasskeySuccess = () => {
    setPasskeyDone(true);
  };

  const handleRealkeyFinish = (success) => {
    setRealkeyResult(success ? 'success' : 'failure');
  };

  if (realkeyResult === 'success') {
    return (
      <div className="max-w-2xl mx-auto mt-8">
        <Card className="border-success/40 bg-success/5 p-8 text-center">
          <CheckCircle className="w-16 h-16 text-success mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-success mb-6 tracking-widest">PAYMENT AUTHORIZED</h2>
          
          <div className="bg-navy-bg border border-navy-border rounded-lg p-6 text-left space-y-4 max-w-md mx-auto mb-8">
            <div className="flex justify-between border-b border-navy-border pb-2">
              <span className="text-text-muted">Payment:</span>
              <span className="font-bold text-text-main">{formatINR(approval.amount)}</span>
            </div>
            <div className="flex justify-between border-b border-navy-border pb-2">
              <span className="text-text-muted">Vendor:</span>
              <span className="font-medium text-text-main">{approval.vendor}</span>
            </div>
            <div className="flex justify-between border-b border-navy-border pb-2">
              <span className="text-text-muted">Authorization:</span>
              <span className="font-medium text-success flex items-center"><CheckCircle className="w-3.5 h-3.5 mr-1" /> REALKEY VERIFIED</span>
            </div>
            <div className="flex justify-between border-b border-navy-border pb-2">
              <span className="text-text-muted">Approval:</span>
              <span className="font-medium text-text-main">Demo User</span>
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
            <ul className="list-disc pl-5 space-y-1">
              <li>Signature invalid</li>
              <li>Payment bundle mismatch (tamper detected)</li>
            </ul>
          </div>
          
          <Button onClick={() => {
            setPasskeyDone(false);
            setRealkeyResult(null);
            setSimulateFailure(false);
          }}>Try Again</Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex items-center space-x-4 mb-2">
        <Link to={`/payments/${id}`} className="text-text-muted hover:text-text-main">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-text-main">Approve Payment</h1>
          <p className="text-sm text-text-muted mt-1">Review the exact payment details before authorizing.</p>
        </div>
      </div>
      
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
          <PaymentBundle approval={approval} />
          
          {passkeyDone && (
            <RealKeyStatus 
              active={true} 
              onSuccess={handleRealkeyFinish} 
              failSimulation={simulateFailure}
            />
          )}
          
          {!passkeyDone && (
            <PasskeyApproval 
              onApprove={handlePasskeySuccess} 
              disabled={disabled} 
              disabledReason={disabledReason}
            />
          )}
        </div>
        
        <div className="lg:col-span-1 space-y-6">
          <ApprovalRequirements approval={approval} />
          <SecurityDetails />
        </div>
      </div>
    </div>
  );
}
