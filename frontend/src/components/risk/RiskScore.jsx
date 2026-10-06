import clsx from 'clsx';
import Card from '../common/Card';

export default function RiskScore({ riskScore, riskLevel, fraudProbability, modelVersion }) {
  const getRiskColor = (level) => {
    switch (level) {
      case 'LOW': return 'text-success border-success';
      case 'MEDIUM': return 'text-warning border-warning';
      case 'HIGH': return 'text-danger border-danger';
      case 'CRITICAL': return 'text-danger border-danger';
      default: return 'text-text-muted border-navy-border';
    }
  };

  const getRiskStrokeColor = (level) => {
    switch (level) {
      case 'LOW': return '#10B981';
      case 'MEDIUM': return '#F59E0B';
      case 'HIGH': return '#EF4444';
      case 'CRITICAL': return '#EF4444';
      default: return '#1E2536';
    }
  };

  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference - (riskScore / 100) * circumference;

  return (
    <Card className="flex flex-col items-center justify-center h-full min-h-[250px]">
      <div className="relative flex items-center justify-center w-32 h-32 mb-4">
        <svg className="w-full h-full transform -rotate-90">
          <circle
            cx="64"
            cy="64"
            r="45"
            stroke="currentColor"
            strokeWidth="8"
            fill="transparent"
            className="text-navy-border"
          />
          <circle
            cx="64"
            cy="64"
            r="45"
            stroke={getRiskStrokeColor(riskLevel)}
            strokeWidth="8"
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-1000 ease-out"
          />
        </svg>
        <div className="absolute flex flex-col items-center justify-center text-center">
          <span className="text-3xl font-bold text-text-main leading-none">{riskScore}</span>
          <span className="text-xs text-text-muted">/ 100</span>
        </div>
      </div>
      
      <div className={clsx("px-3 py-1 rounded-full text-xs font-bold tracking-widest uppercase border bg-navy-bg", getRiskColor(riskLevel))}>
        {riskLevel} RISK
      </div>
      
      <div className="mt-4 flex flex-col items-center text-xs text-text-muted space-y-1">
        <div>Fraud Probability: <span className="font-medium text-text-main">{(fraudProbability * 100).toFixed(0)}%</span></div>
        <div>Model: <span className="font-medium text-text-main">{modelVersion}</span></div>
      </div>
    </Card>
  );
}
