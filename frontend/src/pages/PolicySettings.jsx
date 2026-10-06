import React, { useState, useEffect } from 'react';
import { getPolicy, getPolicyHistory, updatePolicy } from '../api/policyApi';
import { Settings, Save, RotateCcw, AlertTriangle, ShieldCheck, History, Edit2 } from 'lucide-react';
import Card from '../components/common/Card';

export default function PolicySettings() {
  const [activePolicy, setActivePolicy] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  
  // Form State
  const [editMode, setEditMode] = useState(false);
  const [formData, setFormData] = useState(null);
  const [changeReason, setChangeReason] = useState('');

  const fetchPolicyData = async () => {
    try {
      setLoading(true);
      const [policyRes, historyRes] = await Promise.all([
        getPolicy(),
        getPolicyHistory()
      ]);
      setActivePolicy(policyRes);
      setHistory(historyRes);
      setFormData(policyRes.policy);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPolicyData();
  }, []);

  const handleInputChange = (section, field, value) => {
    setFormData(prev => {
      const updated = { ...prev };
      if (section) {
        updated[section] = { ...updated[section], [field]: value };
      } else {
        updated[field] = value;
      }
      return updated;
    });
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!changeReason) {
      setError('A reason for the policy change is required.');
      return;
    }
    
    try {
      setSaving(true);
      setError(null);
      setSuccess(null);
      // Hardcode admin user ID for now since login isn't implemented
      await updatePolicy(formData, 'admin_user', changeReason);
      setSuccess('Policy successfully updated. New version created.');
      setEditMode(false);
      setChangeReason('');
      await fetchPolicyData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setFormData(activePolicy.policy);
    setEditMode(false);
    setError(null);
  };

  if (loading) {
    return <div className="p-8 text-center text-text-muted">Loading policy settings...</div>;
  }

  const inputClass = "w-full bg-navy-bg border border-navy-border rounded-md px-3 py-2 text-text-main placeholder-text-muted focus:outline-none focus:border-primary disabled:opacity-50 disabled:cursor-not-allowed";

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Settings className="h-8 w-8 text-primary" />
            <h1 className="text-2xl font-bold text-text-main">Policy Settings</h1>
          </div>
          <p className="text-sm text-text-muted">Configure ML risk thresholds and financial controls.</p>
        </div>
        {!editMode && (
          <button
            onClick={() => setEditMode(true)}
            className="bg-primary hover:bg-primary/90 text-navy-bg px-4 py-2 rounded font-bold flex items-center gap-2 transition-colors"
          >
            <Edit2 className="h-4 w-4" />
            Edit Policy
          </button>
        )}
      </div>

      {error && (
        <div className="p-4 bg-danger/10 text-danger rounded-md border border-danger/20 flex items-center gap-2">
          <AlertTriangle className="h-5 w-5" />
          {error}
        </div>
      )}
      
      {success && (
        <div className="p-4 bg-success/10 text-success rounded-md border border-success/20 flex items-center gap-2">
          <ShieldCheck className="h-5 w-5" />
          {success}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <form onSubmit={handleSave} className="bg-navy-surface rounded-xl border border-navy-border flex flex-col">
            <div className="p-5 border-b border-navy-border bg-navy-bg/50 flex justify-between items-center">
              <h2 className="font-bold text-text-main">Routing & Threshold Controls</h2>
              <span className="bg-primary/20 text-primary px-3 py-1 rounded font-bold text-xs border border-primary/30">
                Version {activePolicy.version}
              </span>
            </div>

            <div className="p-6 space-y-8">
              {/* Risk Thresholds */}
              <div>
                <h3 className="text-sm font-bold text-primary uppercase tracking-wider mb-4 border-b border-navy-border pb-2">Risk Routing Thresholds</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div>
                    <label className="block text-xs font-medium text-text-muted mb-2">Auto Approve Below</label>
                    <input
                      type="number"
                      step="0.1"
                      disabled={!editMode}
                      value={formData.thresholds.auto_approve_below}
                      onChange={(e) => handleInputChange('thresholds', 'auto_approve_below', parseFloat(e.target.value))}
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-text-muted mb-2">One Signature Below</label>
                    <input
                      type="number"
                      step="0.1"
                      disabled={!editMode}
                      value={formData.thresholds.one_signature_below}
                      onChange={(e) => handleInputChange('thresholds', 'one_signature_below', parseFloat(e.target.value))}
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-text-muted mb-2">Two Signatures Below</label>
                    <input
                      type="number"
                      step="0.1"
                      disabled={!editMode}
                      value={formData.thresholds.two_signature_below}
                      onChange={(e) => handleInputChange('thresholds', 'two_signature_below', parseFloat(e.target.value))}
                      className={inputClass}
                    />
                  </div>
                </div>
                <p className="text-xs text-text-muted mt-3">Scores equal to or above <span className="text-danger font-bold">{formData.thresholds.two_signature_below}</span> are placed on HOLD.</p>
              </div>

              {/* Approval Controls */}
              <div>
                <h3 className="text-sm font-bold text-primary uppercase tracking-wider mb-4 border-b border-navy-border pb-2">Financial Controls</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-xs font-medium text-text-muted mb-2">Auto Approval Cap Amount</label>
                    <input
                      type="number"
                      disabled={!editMode}
                      value={formData.auto_approve_cap_amount}
                      onChange={(e) => handleInputChange(null, 'auto_approve_cap_amount', parseFloat(e.target.value))}
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-text-muted mb-2">Monthly Vendor Cap</label>
                    <input
                      type="number"
                      disabled={!editMode}
                      value={formData.monthly_auto_approved_cap_per_vendor}
                      onChange={(e) => handleInputChange(null, 'monthly_auto_approved_cap_per_vendor', parseFloat(e.target.value))}
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-text-muted mb-2">PO Match Tolerance (%)</label>
                    <input
                      type="number"
                      step="0.1"
                      disabled={!editMode}
                      value={formData.po_match_tolerance_percent}
                      onChange={(e) => handleInputChange(null, 'po_match_tolerance_percent', parseFloat(e.target.value))}
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-text-muted mb-2">Hold Time Limit (Hours)</label>
                    <input
                      type="number"
                      disabled={!editMode}
                      value={formData.hold_time_limit_hours}
                      onChange={(e) => handleInputChange(null, 'hold_time_limit_hours', parseInt(e.target.value))}
                      className={inputClass}
                    />
                  </div>
                </div>
              </div>

              {editMode && (
                <div className="bg-warning/10 p-4 rounded-lg border border-warning/20">
                  <label className="block text-sm font-bold text-warning mb-2">Change Reason (Required for Audit Log)</label>
                  <textarea
                    required
                    value={changeReason}
                    onChange={(e) => setChangeReason(e.target.value)}
                    className="w-full bg-navy-bg border border-warning/30 rounded-md px-3 py-2 text-text-main focus:outline-none focus:border-warning"
                    rows="2"
                    placeholder="E.g., Quarterly threshold adjustment approved by risk committee"
                  ></textarea>
                </div>
              )}
            </div>

            {editMode && (
              <div className="p-4 border-t border-navy-border flex justify-end gap-3 bg-navy-bg/30">
                <button
                  type="button"
                  onClick={handleCancel}
                  className="px-4 py-2 rounded bg-navy-surface border border-navy-border text-text-main font-medium hover:bg-navy-border/50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving || !changeReason}
                  className="bg-primary hover:bg-primary/80 text-navy-bg px-4 py-2 rounded font-bold disabled:opacity-50 transition-colors"
                >
                  {saving ? 'Saving...' : 'Save & Publish Policy'}
                </button>
              </div>
            )}
          </form>
        </div>

        {/* Sidebar / History */}
        <div className="lg:col-span-1 space-y-6">
          <Card className="h-auto">
            <div className="p-4 border-b border-navy-border flex items-center gap-2 bg-navy-bg/50">
              <History className="h-5 w-5 text-text-muted" />
              <h2 className="font-semibold text-text-main">Policy History</h2>
            </div>
            <div className="max-h-[400px] overflow-y-auto divide-y divide-navy-border/50">
              {history.map(item => (
                <div key={item.version} className={`p-4 ${item.active ? 'bg-primary/5' : ''}`}>
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-bold text-text-main">v{item.version}</span>
                    {item.active ? (
                      <span className="text-[10px] bg-success/20 text-success border border-success/30 px-2 py-0.5 rounded font-bold">ACTIVE</span>
                    ) : (
                      <span className="text-[10px] text-text-muted border border-navy-border px-2 py-0.5 rounded font-bold">ARCHIVED</span>
                    )}
                  </div>
                  <div className="text-xs text-text-muted font-mono mb-1">
                    {new Date(item.created_at).toLocaleString()}
                  </div>
                  <div className="text-xs text-text-muted">
                    By: <span className="text-primary">{item.created_by}</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
          
          <div className="bg-primary/10 border border-primary/20 rounded-xl p-5">
            <h3 className="font-bold text-primary mb-2 flex items-center gap-2">
              <ShieldCheck className="h-5 w-5" />
              Immutable Audit Chain
            </h3>
            <p className="text-sm text-text-muted leading-relaxed">
              Every policy update is cryptographically hashed and versioned. Changes apply immediately to new payments, while existing payments respect the policy version they were scored against.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
