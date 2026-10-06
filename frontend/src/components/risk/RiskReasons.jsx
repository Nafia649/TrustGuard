import Card from '../common/Card';
import { Info } from 'lucide-react';

export default function RiskReasons({ reasons }) {
  if (!reasons || reasons.length === 0) {
    return (
      <Card title="Risk Factors" className="h-full flex items-center justify-center text-text-muted text-sm">
        No significant fraud indicators detected.
      </Card>
    );
  }

  return (
    <Card 
      title={
        <div className="flex items-center">
          Top Fraud Indicators
          <div className="group relative ml-2">
            <Info className="w-4 h-4 text-text-muted cursor-pointer hover:text-text-main" />
            <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-navy-surface border border-navy-border rounded text-xs text-text-muted text-center shadow-lg z-10">
              Indicators show which transaction characteristics contributed to the model's risk assessment.
            </div>
          </div>
        </div>
      }
      className="h-full"
    >
      <div className="space-y-4">
        {reasons.map((reason, idx) => (
          <div key={reason.feature || idx} className="flex items-start gap-3 p-3 bg-navy-bg border border-navy-border rounded-lg">
            <div className="w-6 h-6 rounded-full bg-danger/10 text-danger flex items-center justify-center shrink-0 font-bold text-sm">
              {idx + 1}
            </div>
            <div>
              <p className="text-sm font-semibold text-text-main capitalize">
                {reason.description || reason.feature || 'Unknown factor'}
              </p>
              <div className="text-xs text-text-muted mt-1 flex gap-2">
                <span className="uppercase tracking-wider font-semibold text-danger">
                  IMPACT: {reason.impact || 'HIGH'}
                </span>
                <span>•</span>
                <span className="font-mono">{reason.feature}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
