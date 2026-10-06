import Card from '../common/Card';
import Badge from '../common/Badge';
import { AlertTriangle, CheckCircle, Clock } from 'lucide-react';

export default function RoutingCard({ routing, riskLevel }) {
  const { tier, requiredSignatures, completedSignatures } = routing;
  const remaining = requiredSignatures - completedSignatures;

  const getTierDetails = () => {
    switch(tier) {
      case 'AUTO_APPROVE': return { label: 'AUTO APPROVE', icon: CheckCircle, color: 'text-success' };
      case 'ONE_SIGNATURE': return { label: 'ONE SIGNATURE REQUIRED', icon: Clock, color: 'text-warning' };
      case 'TWO_SIGNATURES': return { label: 'TWO SIGNATURES REQUIRED', icon: AlertTriangle, color: 'text-danger' };
      case 'HOLD': return { label: 'PAYMENT ON HOLD', icon: AlertTriangle, color: 'text-danger' };
      default: return { label: tier, icon: Clock, color: 'text-text-muted' };
    }
  };

  const details = getTierDetails();
  const Icon = details.icon;

  return (
    <Card title="Risk-Based Routing" className="h-full">
      <div className="flex flex-col h-full justify-between">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-text-muted">Routing Tier:</span>
            <span className={`text-sm font-bold flex items-center ${details.color}`}>
              <Icon className="w-4 h-4 mr-1.5" />
              {details.label}
            </span>
          </div>
          
          <div className="bg-navy-bg border border-navy-border rounded-md p-4 space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-text-muted">Required Approvals:</span>
              <span className="font-medium text-text-main">{requiredSignatures}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-text-muted">Completed:</span>
              <span className="font-medium text-text-main">{completedSignatures} / {requiredSignatures}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-text-muted">Remaining:</span>
              <span className="font-medium text-text-main">{remaining}</span>
            </div>
          </div>
        </div>
        
        {remaining > 0 && tier !== 'HOLD' && (
          <div className="mt-4 pt-4 border-t border-navy-border">
            <div className="text-xs text-text-muted mb-2">Approvals needed from:</div>
            <div className="flex space-x-2">
              {[...Array(requiredSignatures)].map((_, i) => (
                <div key={i} className="flex items-center space-x-1.5 bg-navy-bg px-2 py-1 rounded border border-navy-border">
                  {i < completedSignatures ? (
                    <CheckCircle className="w-3.5 h-3.5 text-success" />
                  ) : (
                    <Clock className="w-3.5 h-3.5 text-warning" />
                  )}
                  <span className="text-xs">Approver {i + 1}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
