import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { getMockPayment } from '../data/mockPayments';
import { getRiskAnalysis } from '../api/riskApi';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import PaymentSummary from '../components/payment/PaymentSummary';
import ThreeWayMatch from '../components/payment/ThreeWayMatch';
import RiskScore from '../components/risk/RiskScore';
import RiskReasons from '../components/risk/RiskReasons';
import RoutingCard from '../components/risk/RoutingCard';
import { formatINR, formatDate } from '../utils/formatters';
import { CheckCircle, AlertTriangle, ArrowLeft, ArrowRight, Loader2 } from 'lucide-react';

export default function PaymentDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const payment = getMockPayment(id);
  const [riskData, setRiskData] = useState(null);

  useEffect(() => {
    getRiskAnalysis(id)
      .then(data => setRiskData(data))
      .catch(err => console.warn('Could not fetch risk data:', err));
  }, [id]);

  const paymentObj = payment || {
    id: id,
    vendor: riskData?.raw?.vendor_id || 'Acme Industrial Supplies',
    vendorId: riskData?.raw?.vendor_id || 'VEND-001',
    amount: riskData?.raw?.business_checks?.details?.invoice_amount || 45000,
    currency: 'INR',
    bankAccount: 'ACME-BANK-001',
    paymentChannel: 'NEFT',
    description: 'TrustGuard demo payment',
    createdAt: new Date().toISOString(),
    poId: riskData?.poId || 'PO-2026-001',
    invoiceId: riskData?.invoiceId || 'INV-2026-001',
    threeWayMatch: riskData?.threeWayMatch || { po_match: true, grn_match: true, invoice_match: true },
    vendorInfo: { approved: true, typicalAmount: 45000 },
    approvalInfo: { required: 0, completed: 0, remaining: 0, status: 'Authorized' },
  };

  const { threeWayMatch, vendorInfo, approvalInfo } = paymentObj;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-4">
          <Link to="/payments" className="text-text-muted hover:text-text-main">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <h1 className="text-2xl font-bold text-text-main">Payment Details: {paymentObj.id}</h1>
        </div>
        <Button onClick={() => navigate(`/payments/${id}/approve`)}>Review & Approve</Button>
      </div>

      <Card className="bg-navy-surface border-primary/20">
        <PaymentSummary payment={paymentObj} />
      </Card>

      <ThreeWayMatch 
        threeWayMatch={threeWayMatch} 
        poId={paymentObj.poId} 
        invoiceId={paymentObj.invoiceId} 
      />

      {/* Risk Analysis Section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-text-main">Risk Analysis</h3>
          <Button variant="secondary" onClick={() => navigate(`/risk/${paymentObj.id}`)} className="flex items-center text-xs py-1.5 px-3">
            Detailed Analysis <ArrowRight className="w-3.5 h-3.5 ml-1" />
          </Button>
        </div>
        
        {!riskData ? (
          <Card className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-primary animate-spin" />
          </Card>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1 flex flex-col space-y-6">
              <RiskScore 
                riskScore={riskData.riskScore} 
                riskLevel={riskData.riskLevel} 
                fraudProbability={riskData.fraudProbability} 
                modelVersion={riskData.modelVersion} 
              />
              <RoutingCard routing={riskData.routing} riskLevel={riskData.riskLevel} />
            </div>
            <div className="lg:col-span-2">
              <RiskReasons reasons={riskData.reasons} />
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Payment Information">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm border-b border-navy-border pb-4">
              <div><p className="text-text-muted mb-1">Request ID</p><p className="font-medium text-text-main">{paymentObj.id}</p></div>
              <div><p className="text-text-muted mb-1">Created At</p><p className="font-medium text-text-main">{formatDate(paymentObj.createdAt)}</p></div>
              <div><p className="text-text-muted mb-1">Amount</p><p className="font-medium text-text-main">{formatINR(paymentObj.amount)} {paymentObj.currency}</p></div>
              <div><p className="text-text-muted mb-1">Payment Channel</p><p className="font-medium text-text-main">{paymentObj.paymentChannel}</p></div>
              <div className="col-span-2"><p className="text-text-muted mb-1">Bank Account</p><p className="font-medium text-text-main">{paymentObj.bankAccount}</p></div>
              <div className="col-span-2"><p className="text-text-muted mb-1">Description</p><p className="font-medium text-text-main">{paymentObj.description || 'N/A'}</p></div>
            </div>
          </div>
        </Card>

        <div className="space-y-6">
          <Card title="Vendor Information">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><p className="text-text-muted mb-1">Vendor Name</p><p className="font-medium text-text-main">{paymentObj.vendor}</p></div>
              <div><p className="text-text-muted mb-1">Vendor ID</p><p className="font-medium text-text-main">{paymentObj.vendorId}</p></div>
              <div><p className="text-text-muted mb-1">Status</p><p className="font-medium text-text-main">{vendorInfo.approved ? <span className="text-success flex items-center"><CheckCircle className="w-3 h-3 mr-1"/> Approved Vendor</span> : <span className="text-danger flex items-center"><AlertTriangle className="w-3 h-3 mr-1"/> Unverified Vendor</span>}</p></div>
              <div><p className="text-text-muted mb-1">Typical Amount</p><p className="font-medium text-text-main">{vendorInfo.typicalAmount > 0 ? formatINR(vendorInfo.typicalAmount) : 'N/A'}</p></div>
            </div>
          </Card>

          <Card title="Approval Information">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><p className="text-text-muted mb-1">Required Approvals</p><p className="font-medium text-text-main">{approvalInfo.required}</p></div>
              <div><p className="text-text-muted mb-1">Completed</p><p className="font-medium text-text-main">{approvalInfo.completed}</p></div>
              <div><p className="text-text-muted mb-1">Remaining</p><p className="font-medium text-text-main">{approvalInfo.remaining}</p></div>
              <div><p className="text-text-muted mb-1">Current Status</p><p className="font-medium text-text-main">{approvalInfo.status}</p></div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
