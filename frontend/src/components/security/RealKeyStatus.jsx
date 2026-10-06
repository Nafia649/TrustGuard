import { useEffect, useState } from 'react';
import Card from '../common/Card';
import { CheckCircle, Circle, Loader2, XCircle } from 'lucide-react';
import clsx from 'clsx';

export default function RealKeyStatus({ active, onSuccess, failSimulation }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!active) return;

    const timer1 = setTimeout(() => setStep(1), 500);
    const timer2 = setTimeout(() => setStep(2), 1000);
    const timer3 = setTimeout(() => setStep(3), 1500);
    const timer4 = setTimeout(() => setStep(4), 2200);
    const timer5 = setTimeout(() => {
      setStep(5);
      setTimeout(() => onSuccess(!failSimulation), 800);
    }, 2800);

    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      clearTimeout(timer4);
      clearTimeout(timer5);
    };
  }, [active, onSuccess, failSimulation]);

  const stages = [
    { text: "Payment bundle created", completedText: "Payment bundle created" },
    { text: "Payment details fingerprinted", completedText: "Payment fingerprinted" },
    { text: "Passkey approval", completedText: "Passkey approval received" },
    { text: "Signature verification", completedText: failSimulation ? "Signature verification failed" : "Signature verification successful" },
    { text: "Exact payment verified", completedText: failSimulation ? "Payment verification failed" : "Exact payment verified" }
  ];

  return (
    <Card title="REALKEY — Exact Payment Verification" className={clsx("transition-all duration-500", active && !failSimulation && step === 5 ? "border-success/50 bg-success/5" : "")}>
      <div className="space-y-4">
        {stages.map((stage, idx) => {
          const isCompleted = step > idx;
          const isCurrent = step === idx && active;
          const isFailed = failSimulation && isCompleted && idx >= 3;
          
          return (
            <div key={idx} className={clsx("flex items-center space-x-3 transition-opacity duration-300", !isCompleted && !isCurrent ? "opacity-40" : "opacity-100")}>
              {isCompleted ? (
                isFailed ? <XCircle className="w-5 h-5 text-danger shrink-0" /> : <CheckCircle className="w-5 h-5 text-success shrink-0" />
              ) : isCurrent ? (
                <Loader2 className="w-5 h-5 text-primary animate-spin shrink-0" />
              ) : (
                <Circle className="w-5 h-5 text-text-muted shrink-0" />
              )}
              
              <span className={clsx("text-sm", isCompleted ? (isFailed ? "text-danger font-medium" : "text-success font-medium") : "text-text-main")}>
                {isCompleted ? stage.completedText : stage.text}
              </span>
            </div>
          );
        })}
      </div>
      
      {step === 5 && !failSimulation && (
        <div className="mt-6 pt-4 border-t border-success/30 text-center">
          <h4 className="text-xl font-bold text-success tracking-widest">PAYMENT AUTHORIZED</h4>
        </div>
      )}

      {step === 5 && failSimulation && (
        <div className="mt-6 pt-4 border-t border-danger/30 text-center">
          <h4 className="text-xl font-bold text-danger tracking-widest">AUTHORIZATION FAILED</h4>
        </div>
      )}
    </Card>
  );
}
