import { useState } from 'react';
import Button from '../common/Button';

export default function PaymentForm({ onSubmit, onCancel, isSubmitting, success }) {
  const [formData, setFormData] = useState({
    vendor: '',
    vendorId: '',
    amount: '',
    currency: 'INR'
  });
  
  const [errors, setErrors] = useState({});

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }));
    }
  };

  const validate = () => {
    const newErrors = {};
    if (!formData.vendor.trim()) newErrors.vendor = 'Vendor is required';
    if (!formData.vendorId.trim()) newErrors.vendorId = 'Vendor ID is required';
    
    if (!formData.amount) {
      newErrors.amount = 'Amount is required';
    } else if (isNaN(Number(formData.amount)) || Number(formData.amount) <= 0) {
      newErrors.amount = 'Amount must be a number greater than 0';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (validate()) {
      onSubmit({
        ...formData,
        amount: Number(formData.amount)
      });
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-1">
          <label className="text-sm font-medium text-text-muted">Vendor <span className="text-danger">*</span></label>
          <input type="text" name="vendor" value={formData.vendor} onChange={handleChange} className="w-full bg-navy-bg border border-navy-border rounded-md px-3 py-2 text-text-main focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary placeholder-navy-border" placeholder="e.g. ABC Suppliers" disabled={isSubmitting || success} />
          {errors.vendor && <p className="text-xs text-danger">{errors.vendor}</p>}
        </div>

        <div className="space-y-1">
          <label className="text-sm font-medium text-text-muted">Vendor ID <span className="text-danger">*</span></label>
          <input type="text" name="vendorId" value={formData.vendorId} onChange={handleChange} className="w-full bg-navy-bg border border-navy-border rounded-md px-3 py-2 text-text-main focus:outline-none focus:border-primary" placeholder="e.g. V001" disabled={isSubmitting || success} />
          {errors.vendorId && <p className="text-xs text-danger">{errors.vendorId}</p>}
        </div>

        <div className="space-y-1">
          <label className="text-sm font-medium text-text-muted">Amount <span className="text-danger">*</span></label>
          <div className="relative">
            <span className="absolute left-3 top-2 text-text-muted">₹</span>
            <input type="number" name="amount" value={formData.amount} onChange={handleChange} className="w-full bg-navy-bg border border-navy-border rounded-md pl-8 pr-3 py-2 text-text-main focus:outline-none focus:border-primary" placeholder="0.00" disabled={isSubmitting || success} />
          </div>
          {errors.amount && <p className="text-xs text-danger">{errors.amount}</p>}
        </div>

        <div className="space-y-1">
          <label className="text-sm font-medium text-text-muted">Currency</label>
          <select name="currency" value={formData.currency} onChange={handleChange} className="w-full bg-navy-bg border border-navy-border rounded-md px-3 py-2 text-text-main focus:outline-none focus:border-primary" disabled={isSubmitting || success}>
            <option value="INR">INR (₹)</option>
            <option value="USD">USD ($)</option>
            <option value="EUR">EUR (€)</option>
          </select>
        </div>

        <div className="md:col-span-2 space-y-1">
          <label className="text-sm font-medium text-text-muted">Supporting Document</label>
          <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-navy-border border-dashed rounded-md hover:border-primary/50 transition-colors">
            <div className="space-y-1 text-center">
              <svg className="mx-auto h-12 w-12 text-text-muted" stroke="currentColor" fill="none" viewBox="0 0 48 48" aria-hidden="true">
                <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <div className="flex text-sm text-text-muted justify-center">
                <label htmlFor="file-upload" className="relative cursor-pointer bg-navy-bg rounded-md font-medium text-primary hover:text-primary/80 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-primary">
                  <span>Upload a file</span>
                  <input id="file-upload" name="file-upload" type="file" className="sr-only" disabled={isSubmitting || success} />
                </label>
                <p className="pl-1">or drag and drop</p>
              </div>
              <p className="text-xs text-text-muted">
                PDF, PNG, JPG up to 10MB
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="pt-4 border-t border-navy-border flex justify-end space-x-4">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={isSubmitting || success}>Cancel</Button>
        <Button type="submit" disabled={isSubmitting || success} className="w-full sm:w-auto">
          {isSubmitting ? 'Submitting...' : 'Create Payment Request'}
        </Button>
      </div>
    </form>
  );
}
