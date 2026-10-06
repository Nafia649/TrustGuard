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
    if (payment) {
      getRiskAnalysis(id).then(data => setRiskData(data));
    }
  }, [id, payment]);

  if (!payment) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-bold text-text-main">Payment Not Found</h2>
        <p className="text-text-muted mt-2">The request {id} could not be located.</p>
        <Link to="/payments" className="text-primary mt-4 inline-block hover:underline">← Back to Payments</Link>
      </div>
    );
  }

  const { threeWayMatch, vendorInfo, approvalInfo } = payment;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-4">
          <Link to="/payments" className="text-text-muted hover:text-text-main">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <h1 className="text-2xl font-bold text-text-main">Payment Details: {payment.id}</h1>
        </div>
        <Button onClick={() => navigate(`/payments/${id}/approve`)}>Review & Approve</Button>
      </div>

      <Card className="bg-navy-surface border-primary/20">
        <PaymentSummary payment={payment} />
      </Card>

      <ThreeWayMatch 
        threeWayMatch={threeWayMatch} 
        poId={payment.poId} 
        invoiceId={payment.invoiceId} 
      />

      {/* Risk Analysis Section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-text-main">Risk Analysis</h3>
          <Button variant="secondary" onClick={() => navigate(`/risk/${payment.id}`)} className="flex items-center text-xs py-1.5 px-3">
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
              <div><p className="text-text-muted mb-1">Request ID</p><p className="font-medium text-text-main">{payment.id}</p></div>
              <div><p className="text-text-muted mb-1">Created At</p><p className="font-medium text-text-main">{formatDate(payment.createdAt)}</p></div>
              <div><p className="text-text-muted mb-1">Amount</p><p className="font-medium text-text-main">{formatINR(payment.amount)} {payment.currency}</p></div>
              <div><p className="text-text-muted mb-1">Payment Channel</p><p className="font-medium text-text-main">{payment.paymentChannel}</p></div>
              <div className="col-span-2"><p className="text-text-muted mb-1">Bank Account</p><p className="font-medium text-text-main">{payment.bankAccount}</p></div>
              <div className="col-span-2"><p className="text-text-muted mb-1">Description</p><p className="font-medium text-text-main">{payment.description || 'N/A'}</p></div>
            </div>
          </div>
        </Card>

        <div className="space-y-6">
          <Card title="Vendor Information">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><p className="text-text-muted mb-1">Vendor Name</p><p className="font-medium text-text-main">{payment.vendor}</p></div>
              <div><p className="text-text-muted mb-1">Vendor ID</p><p className="font-medium text-text-main">{payment.vendorId}</p></div>
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
