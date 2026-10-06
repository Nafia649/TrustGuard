import Card from '../common/Card';
import { Info } from 'lucide-react';

export default function RiskReasons({ reasons }) {
  const increasesRisk = reasons.filter(r => r.direction === 'increases_risk').sort((a, b) => b.contribution - a.contribution);
  const reducesRisk = reasons.filter(r => r.direction === 'reduces_risk').sort((a, b) => a.contribution - b.contribution); // a.contribution is negative

  const maxContribution = Math.max(...reasons.map(r => Math.abs(r.contribution)), 1);

  const renderBar = (reason, isPositive) => {
    const percentage = (Math.abs(reason.contribution) / maxContribution) * 100;
    const colorClass = isPositive ? 'bg-danger' : 'bg-success';
    const textColor = isPositive ? 'text-danger' : 'text-success';

    return (
      <div key={reason.feature} className="mb-4">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-text-main pr-2 truncate">{reason.label}</span>
          <span className={`font-medium ${textColor} shrink-0`}>
            {isPositive ? '+' : ''}{reason.contribution}
          </span>
        </div>
        <div className="w-full bg-navy-border rounded-full h-1.5 flex">
          {!isPositive && <div className="flex-1"></div>}
          <div className={`h-1.5 rounded-full ${colorClass}`} style={{ width: `${percentage}%` }}></div>
          {isPositive && <div className="flex-1"></div>}
        </div>
      </div>
    );
  };

  return (
    <Card 
      title={
        <div className="flex items-center">
          Why is this payment risky?
          <div className="group relative ml-2">
            <Info className="w-4 h-4 text-text-muted cursor-pointer hover:text-text-main" />
            <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-navy-surface border border-navy-border rounded text-xs text-text-muted text-center shadow-lg z-10">
              SHAP explanations show which transaction characteristics contributed to the model's risk assessment.
            </div>
          </div>
        </div>
      }
      className="h-full"
    >
      <div className="space-y-6">
        {increasesRisk.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Risk Increasing Factors</h4>
            {increasesRisk.map(r => renderBar(r, true))}
          </div>
        )}
        
        {reducesRisk.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Risk Reducing Factors</h4>
            {reducesRisk.map(r => renderBar(r, false))}
          </div>
        )}
      </div>
    </Card>
  );
}
