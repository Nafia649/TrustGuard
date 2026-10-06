import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/common/Card';
import PaymentForm from '../components/payment/PaymentForm';
import { addMockPayment } from '../data/mockPayments';

export default function NewPayment() {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  
  const handleSubmit = (formData) => {
    setIsSubmitting(true);
    
    // Simulate network request
    setTimeout(() => {
      const newPayment = addMockPayment(formData);
      setIsSubmitting(false);
      setSuccess(true);
      
      // Navigate to details after brief success message
      setTimeout(() => {
        navigate(`/payments/${newPayment.id}`);
      }, 1000);
    }, 1000);
  };

  const handleCancel = () => {
    navigate('/payments');
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-main">New Payment Request</h1>
          <p className="text-sm text-text-muted mt-1">Submit a new payment for authorization.</p>
        </div>
      </div>

      {success && (
        <div className="p-4 bg-success/10 border border-success/30 rounded-md flex items-center text-success font-medium">
          <svg className="w-5 h-5 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
          </svg>
          Payment request created successfully. Redirecting...
        </div>
      )}

      <Card>
        <PaymentForm 
          onSubmit={handleSubmit} 
          onCancel={handleCancel} 
          isSubmitting={isSubmitting} 
          success={success} 
        />
      </Card>
    </div>
  );
}
