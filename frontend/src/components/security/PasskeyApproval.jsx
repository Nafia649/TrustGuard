import { useState } from 'react';
import Card from '../common/Card';
import Button from '../common/Button';
import { Fingerprint, CheckCircle, Loader2 } from 'lucide-react';

export default function PasskeyApproval({ onApprove, disabled, disabledReason }) {
  const [status, setStatus] = useState('ready'); // ready, authenticating, success

  const handleApprove = () => {
    setStatus('authenticating');
    
    // TODO: The security/backend teammate will replace this mock implementation 
    // with the actual WebAuthn/Passkey flow.
    // approveWithPasskey();
    
    setTimeout(() => {
      setStatus('success');
      setTimeout(() => {
        onApprove();
        setStatus('ready');
      }, 1000);
    }, 2000);
  };

  if (disabled) {
    return (
      <Card className="text-center p-8 bg-navy-surface border-navy-border opacity-70">
        <div className="w-16 h-16 rounded-full bg-navy-border/50 flex items-center justify-center mx-auto mb-4">
          <Fingerprint className="w-8 h-8 text-text-muted" />
        </div>
        <h4 className="text-lg font-bold text-text-muted mb-2">Approval unavailable</h4>
        <p className="text-sm text-text-muted">{disabledReason}</p>
      </Card>
    );
  }

  return (
    <Card className="text-center p-8 border-primary/40 relative overflow-hidden">
      {status === 'ready' && (
        <>
          <div className="w-20 h-20 rounded-full bg-primary/20 flex items-center justify-center mx-auto mb-6">
            <Fingerprint className="w-10 h-10 text-primary animate-pulse" />
          </div>
          <h4 className="text-xl font-bold text-text-main mb-2">Ready for secure approval</h4>
          <p className="text-sm text-text-muted mb-8">Confirm using your device passkey.</p>
          <Button onClick={handleApprove} className="w-full sm:w-auto px-8 py-3 text-lg font-bold">
            Approve with Passkey
          </Button>
        </>
      )}

      {status === 'authenticating' && (
        <>
          <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-6">
            <Loader2 className="w-10 h-10 text-primary animate-spin" />
          </div>
          <h4 className="text-xl font-bold text-text-main mb-2">Waiting for passkey confirmation...</h4>
          <p className="text-sm text-text-muted mb-8 text-warning">Please check your device.</p>
          <Button disabled className="w-full sm:w-auto px-8 py-3 text-lg opacity-50">
            Authenticating...
          </Button>
        </>
      )}

      {status === 'success' && (
        <>
          <div className="w-20 h-20 rounded-full bg-success/20 flex items-center justify-center mx-auto mb-6">
            <CheckCircle className="w-10 h-10 text-success" />
          </div>
          <h4 className="text-xl font-bold text-success mb-2">Passkey authentication successful</h4>
          <p className="text-sm text-text-muted mb-8">Continuing to verification...</p>
        </>
      )}
    </Card>
  );
}
