import Card from '../common/Card';
import { CheckCircle, Clock, AlertTriangle, XCircle } from 'lucide-react';

export default function ApprovalRequirements({ approval }) {
  const { routingTier, requiredSignatures, completedSignatures, approvers } = approval;
  const isHold = routingTier === 'HOLD';
  const isAuto = routingTier === 'AUTO_APPROVE';

  if (isHold) {
    return (
      <Card title="Approval Requirement" className="border-danger/30">
        <div className="flex flex-col items-center justify-center p-6 text-center">
          <AlertTriangle className="w-12 h-12 text-danger mb-4" />
          <h4 className="text-xl font-bold text-danger mb-2">PAYMENT ON HOLD</h4>
          <p className="text-text-muted text-sm">This payment cannot be approved due to critical risk factors.</p>
        </div>
      </Card>
    );
  }

  if (isAuto) {
    return (
      <Card title="Approval Requirement" className="border-success/30">
        <div className="flex flex-col items-center justify-center p-6 text-center">
          <CheckCircle className="w-12 h-12 text-success mb-4" />
          <h4 className="text-xl font-bold text-success mb-2">AUTO APPROVAL</h4>
          <p className="text-text-muted text-sm">This payment does not require manual signature.</p>
        </div>
      </Card>
    );
  }

  return (
    <Card title="Approval Requirement">
      <div className="mb-6 pb-4 border-b border-navy-border">
        <h4 className="font-bold text-text-main mb-1">
          {routingTier.replace('_', ' ')}
        </h4>
        <p className="text-sm text-text-muted">
          {completedSignatures} / {requiredSignatures} completed
        </p>
      </div>

      <div className="space-y-4">
        <h5 className="text-xs uppercase text-text-muted font-semibold tracking-wider">Approvals</h5>
        
        {approvers.map((appr, idx) => (
          <div key={idx} className="flex justify-between items-center p-3 bg-success/10 border border-success/30 rounded-md">
            <div className="flex items-center">
              <CheckCircle className="w-4 h-4 text-success mr-3" />
              <span className="text-sm font-medium text-text-main">Approver {idx + 1}: {appr.name}</span>
            </div>
            <span className="text-xs text-text-muted">Completed</span>
          </div>
        ))}
        
        {[...Array(requiredSignatures - completedSignatures)].map((_, idx) => (
          <div key={`pending-${idx}`} className="flex justify-between items-center p-3 bg-navy-bg border border-navy-border rounded-md opacity-70">
            <div className="flex items-center">
              <Clock className="w-4 h-4 text-warning mr-3" />
              <span className="text-sm text-text-muted">Approver {completedSignatures + idx + 1}: Pending</span>
            </div>
          </div>
        ))}
      </div>
      
      {requiredSignatures > 1 && (
        <div className="mt-6 p-3 bg-primary/10 rounded-md border border-primary/20 text-xs text-primary/90 flex items-start">
          <AlertTriangle className="w-4 h-4 mr-2 shrink-0 mt-0.5" />
          Payment cannot be released until both required approvals are completed.
        </div>
      )}
    </Card>
  );
}
