import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getMockPayment } from '../data/mockPayments';
import { getRiskAnalysis } from '../api/riskApi';
import RiskScore from '../components/risk/RiskScore';
import RiskReasons from '../components/risk/RiskReasons';
import RoutingCard from '../components/risk/RoutingCard';
import ThreeWayMatch from '../components/payment/ThreeWayMatch';
import { formatINR } from '../utils/formatters';
import { ArrowLeft, Loader2, AlertTriangle, CheckCircle } from 'lucide-react';
import clsx from 'clsx';

export default function RiskAnalysis() {
  const { id } = useParams();
  const payment = getMockPayment(id);
  const [riskData, setRiskData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getRiskAnalysis(id).then(data => {
      setRiskData(data);
      setLoading(false);
    });
  }, [id]);

  if (!payment) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-bold text-text-main">Payment Not Found</h2>
        <Link to="/payments" className="text-primary mt-4 inline-block hover:underline">← Back to Payments</Link>
      </div>
    );
  }

  if (loading || !riskData) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  const getBannerColor = (level) => {
    switch (level) {
      case 'LOW': return 'bg-success/10 border-success/30 text-success';
      case 'MEDIUM': return 'bg-warning/10 border-warning/30 text-warning';
      case 'HIGH': return 'bg-danger/10 border-danger/30 text-danger';
      case 'CRITICAL': return 'bg-danger/20 border-danger text-danger';
      default: return 'bg-navy-surface border-navy-border text-text-muted';
    }
  };

  const Icon = riskData.riskLevel === 'LOW' ? CheckCircle : AlertTriangle;

  return (
    <div className="space-y-6">
      <div className="flex items-center space-x-4 mb-2">
        <Link to={`/payments/${id}`} className="text-text-muted hover:text-text-main">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <h1 className="text-2xl font-bold text-text-main">Detailed Risk Analysis: {payment.id}</h1>
      </div>

      <div className={clsx("p-4 border rounded-lg flex items-center shadow-lg", getBannerColor(riskData.riskLevel))}>
        <Icon className="w-6 h-6 mr-3" />
        <div>
          <h2 className="font-bold text-lg">{riskData.riskLevel} RISK</h2>
          <p className="text-sm opacity-90">Payment of {formatINR(payment.amount)} to {payment.vendor}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <RiskScore 
            riskScore={riskData.riskScore} 
            riskLevel={riskData.riskLevel} 
            fraudProbability={riskData.fraudProbability} 
            modelVersion={riskData.modelVersion} 
          />
        </div>
        <div className="lg:col-span-2">
          <RiskReasons reasons={riskData.reasons} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RoutingCard routing={riskData.routing} riskLevel={riskData.riskLevel} />
        <div className="bg-navy-surface border border-navy-border rounded-xl p-5">
           <ThreeWayMatch 
              threeWayMatch={payment.threeWayMatch} 
              poId={payment.poId} 
              invoiceId={payment.invoiceId} 
            />
        </div>
      </div>
    </div>
  );
}
