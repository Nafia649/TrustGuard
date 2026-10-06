import { useState, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import Card from '../components/common/Card';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  ArrowRight,
  Edit3,
  Check,
  Building,
  Receipt,
  CreditCard,
  ShieldCheck,
  AlertCircle,
  Calendar,
  DollarSign,
  FileUp,
} from 'lucide-react';
import { uploadInvoice, reviewInvoice, createPaymentFromInvoice } from '../api/invoiceApi';
import { formatINR } from '../utils/formatters';

export default function InvoiceUpload() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [docData, setDocData] = useState(null);

  const [isEditing, setIsEditing] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [reviewForm, setReviewForm] = useState({
    vendor_id: '',
    vendor_name: '',
    invoice_id: '',
    amount: '',
    currency: 'INR',
    bank_account: '',
    po_id: '',
  });

  const [creatingPayment, setCreatingPayment] = useState(false);
  const [createdPaymentResult, setCreatedPaymentResult] = useState(null);
  const [error, setError] = useState(null);

  // 1. Select file
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      setDocData(null);
      setCreatedPaymentResult(null);
      setError(null);
      setIsEditing(false);
    }
  };

  // 2. Upload file & run OCR extraction
  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setError(null);
    setCreatedPaymentResult(null);

    try {
      const data = await uploadInvoice(selectedFile);
      setDocData(data);
      populateReviewForm(data);
    } catch (err) {
      setError(err.message || 'Failed to upload and process invoice document.');
    } finally {
      setUploading(false);
    }
  };

  const populateReviewForm = (data) => {
    const ext = data?.extracted_data || {};
    const vm = data?.vendor_match || {};
    setReviewForm({
      vendor_id: ext.vendor_id || vm.matched_vendor_id || '',
      vendor_name: ext.vendor_name || vm.matched_vendor_name || '',
      invoice_id: ext.invoice_id || '',
      amount: ext.total_amount != null ? String(ext.total_amount) : '',
      currency: ext.currency || 'INR',
      bank_account: ext.bank_account || '',
      po_id: ext.po_id || '',
    });
  };

  // 3. Save Review / Edit OCR details
  const handleSaveReview = async (e) => {
    e.preventDefault();
    if (!docData?.document_id) return;

    setReviewing(true);
    setError(null);

    try {
      const updatedDoc = await reviewInvoice(docData.document_id, {
        vendor_id: reviewForm.vendor_id || undefined,
        vendor_name: reviewForm.vendor_name || undefined,
        invoice_id: reviewForm.invoice_id,
        amount: parseFloat(reviewForm.amount) || 0,
        currency: reviewForm.currency.toUpperCase(),
        bank_account: reviewForm.bank_account || undefined,
        po_id: reviewForm.po_id || undefined,
      });
      setDocData(updatedDoc);
      setIsEditing(false);
    } catch (err) {
      setError(err.message || 'Failed to update invoice review details.');
    } finally {
      setReviewing(false);
    }
  };

  // 4. Create Payment Request from extracted invoice
  const handleCreatePaymentRequest = async () => {
    if (!docData?.document_id) return;

    setCreatingPayment(true);
    setError(null);

    try {
      const result = await createPaymentFromInvoice(docData.document_id, {
        vendor_id: reviewForm.vendor_id || undefined,
        vendor_name: reviewForm.vendor_name || undefined,
        invoice_id: reviewForm.invoice_id || docData.extracted_data?.invoice_id,
        amount: parseFloat(reviewForm.amount) || docData.extracted_data?.total_amount || 0,
        currency: reviewForm.currency || docData.extracted_data?.currency || 'INR',
        bank_account: reviewForm.bank_account || docData.extracted_data?.bank_account,
        po_id: reviewForm.po_id || docData.extracted_data?.po_id,
      });
      setCreatedPaymentResult(result);
    } catch (err) {
      setError(err.message || 'Failed to create payment request from invoice.');
    } finally {
      setCreatingPayment(false);
    }
  };

  const ext = docData?.extracted_data || {};
  const vm = docData?.vendor_match || {};
  const confidencePercent = ext.confidence != null ? `${(ext.confidence * 100).toFixed(1)}%` : 'N/A';

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-main flex items-center gap-2">
            <FileUp className="w-7 h-7 text-primary" />
            Invoice Document OCR & Extraction
          </h1>
          <p className="text-xs text-text-muted mt-1">
            Upload vendor invoices (PDF, PNG, JPG) to extract structured payment metadata, match vendor details, and initiate payment requests.
          </p>
        </div>
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="p-4 bg-danger/10 border border-danger/30 rounded-xl flex items-start gap-3 text-danger">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="font-semibold text-sm">Processing Exception / Validation Alert</h4>
            <p className="text-xs mt-1 text-danger/90 leading-relaxed">{error}</p>
          </div>
        </div>
      )}

      {/* Upload Drop Zone Card */}
      <Card title="Upload Vendor Invoice PDF" className="border-navy-border">
        <div className="space-y-4">
          <div
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-navy-border hover:border-primary/50 rounded-xl p-8 text-center cursor-pointer transition-colors bg-navy-bg/50 group"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              onChange={handleFileChange}
              className="hidden"
            />
            <div className="w-14 h-14 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform">
              <Upload className="w-7 h-7 text-primary" />
            </div>
            <h3 className="font-semibold text-text-main text-base">
              {selectedFile ? selectedFile.name : 'Click to select or drag invoice PDF/image'}
            </h3>
            <p className="text-xs text-text-muted mt-1">
              Supports demo fixtures: <code className="text-primary font-mono">INV-DEMO-001.pdf</code> through <code className="text-primary font-mono">INV-DEMO-010.pdf</code> (Max 10 MB)
            </p>
            {selectedFile && (
              <div className="mt-3 inline-flex items-center gap-2 px-3 py-1 rounded-full bg-navy-surface border border-navy-border text-xs text-text-main">
                <FileText className="w-3.5 h-3.5 text-primary" />
                <span>{selectedFile.name}</span>
                <span className="text-text-muted">({(selectedFile.size / 1024).toFixed(1)} KB)</span>
              </div>
            )}
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
            <div className="text-xs text-text-muted">
              Demo sample fixtures are located in <code className="text-text-main">demo-invoices/</code>
            </div>
            <Button
              onClick={handleUpload}
              disabled={!selectedFile || uploading}
              className="w-full sm:w-auto flex items-center justify-center gap-2"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-navy-bg" />
                  <span>Extracting invoice...</span>
                </>
              ) : (
                <>
                  <FileUp className="w-4 h-4 text-navy-bg" />
                  <span>Upload & Extract OCR</span>
                </>
              )}
            </Button>
          </div>
        </div>
      </Card>

      {/* Loading Overlay State */}
      {uploading && (
        <Card className="text-center py-12 bg-navy-surface border-primary/30">
          <div className="flex flex-col items-center justify-center space-y-3">
            <Loader2 className="w-10 h-10 text-primary animate-spin" />
            <h3 className="text-lg font-bold text-text-main">Extracting invoice...</h3>
            <p className="text-xs text-text-muted max-w-md">
              Running OCR text extraction, parsing invoice fields, and cross-referencing vendor master database...
            </p>
          </div>
        </Card>
      )}

      {/* Extracted Document Results */}
      {docData && !uploading && (
        <div className="space-y-6">
          {/* Summary Status Bar */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="bg-navy-surface border-navy-border">
              <div className="text-xs text-text-muted">Document Status</div>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant={docData.status === 'EXTRACTED' ? 'success' : 'primary'}>
                  {docData.status}
                </Badge>
                <span className="text-xs text-text-muted">{docData.document_id}</span>
              </div>
            </Card>

            <Card className="bg-navy-surface border-navy-border">
              <div className="text-xs text-text-muted">OCR Confidence Score</div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xl font-bold text-primary">{confidencePercent}</span>
                <span className="text-xs text-text-muted">Structured parsing accuracy</span>
              </div>
            </Card>

            <Card className="bg-navy-surface border-navy-border">
              <div className="text-xs text-text-muted">Vendor Match Result</div>
              <div className="flex items-center gap-2 mt-1">
                <Badge status={vm.is_approved ? 'APPROVED' : 'HOLD'}>
                  {vm.is_approved ? 'APPROVED VENDOR' : 'UNAPPROVED VENDOR'}
                </Badge>
                <span className="text-xs text-text-muted font-mono">{vm.status || 'UNKNOWN'}</span>
              </div>
            </Card>
          </div>

          {/* OCR Data Grid + Vendor Match Details */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Extracted Invoice Data Card */}
            <div className="lg:col-span-2 space-y-6">
              <Card
                title="Extracted Invoice Data"
                action={
                  <Button
                    variant="secondary"
                    className="py-1 px-3 text-xs flex items-center gap-1.5"
                    onClick={() => setIsEditing(!isEditing)}
                  >
                    <Edit3 className="w-3.5 h-3.5 text-primary" />
                    <span>{isEditing ? 'Cancel Edit' : 'Review / Edit'}</span>
                  </Button>
                }
              >
                {isEditing ? (
                  /* Edit / Review Form */
                  <form onSubmit={handleSaveReview} className="space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs text-text-muted mb-1 font-medium">Vendor Name</label>
                        <input
                          type="text"
                          value={reviewForm.vendor_name}
                          onChange={(e) => setReviewForm({ ...reviewForm, vendor_name: e.target.value })}
                          className="w-full bg-navy-bg border border-navy-border rounded-md px-3 py-2 text-sm text-text-main focus:outline-none focus:border-primary"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-text-muted mb-1 font-medium">Vendor ID</label>
                        <input
                          type="text"
                          value={reviewForm.vendor_id}
                          onChange={(e) => setReviewForm({ ...reviewForm, vendor_id: e.target.value })}
                          placeholder="e.g. VEND-001"
                          className="w-full bg-navy-bg border border-navy-border rounded-md px-3 py-2 text-sm text-text-main focus:outline-none focus:border-primary font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-text-muted mb-1 font-medium">Invoice Number / ID *</label>
                        <input
                          type="text"
                          required
                          value={reviewForm.invoice_id}
                          onChange={(e) => setReviewForm({ ...reviewForm, invoice_id: e.target.value })}
                          className="w-full bg-navy-bg border border-navy-border rounded-md px-3 py-2 text-sm text-text-main focus:outline-none focus:border-primary font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-text-muted mb-1 font-medium">Amount *</label>
                        <input
                          type="number"
                          step="0.01"
                          required
                          value={reviewForm.amount}
                          onChange={(e) => setReviewForm({ ...reviewForm, amount: e.target.value })}
                          className="w-full bg-navy-bg border border-navy-border rounded-md px-3 py-2 text-sm text-text-main focus:outline-none focus:border-primary font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-text-muted mb-1 font-medium">Currency</label>
                        <input
                          type="text"
                          value={reviewForm.currency}
                          onChange={(e) => setReviewForm({ ...reviewForm, currency: e.target.value })}
                          className="w-full bg-navy-bg border border-navy-border rounded-md px-3 py-2 text-sm text-text-main focus:outline-none focus:border-primary font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-text-muted mb-1 font-medium">Bank Account</label>
                        <input
                          type="text"
                          value={reviewForm.bank_account}
                          onChange={(e) => setReviewForm({ ...reviewForm, bank_account: e.target.value })}
                          className="w-full bg-navy-bg border border-navy-border rounded-md px-3 py-2 text-sm text-text-main focus:outline-none focus:border-primary font-mono"
                        />
                      </div>
                      <div className="sm:col-span-2">
                        <label className="block text-xs text-text-muted mb-1 font-medium">Linked PO Number</label>
                        <input
                          type="text"
                          value={reviewForm.po_id}
                          onChange={(e) => setReviewForm({ ...reviewForm, po_id: e.target.value })}
                          placeholder="e.g. PO-2026-001"
                          className="w-full bg-navy-bg border border-navy-border rounded-md px-3 py-2 text-sm text-text-main focus:outline-none focus:border-primary font-mono"
                        />
                      </div>
                    </div>

                    <div className="flex justify-end gap-3 pt-2">
                      <Button variant="secondary" type="button" onClick={() => setIsEditing(false)}>
                        Cancel
                      </Button>
                      <Button variant="primary" type="submit" disabled={reviewing}>
                        {reviewing ? 'Saving Review...' : 'Save & Re-evaluate Vendor'}
                      </Button>
                    </div>
                  </form>
                ) : (
                  /* Display OCR Readout */
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 p-4 bg-navy-bg/50 rounded-xl border border-navy-border">
                      <div>
                        <span className="text-xs text-text-muted flex items-center gap-1">
                          <Building className="w-3.5 h-3.5 text-primary" /> Vendor Name
                        </span>
                        <p className="text-sm font-semibold text-text-main mt-1">
                          {ext.vendor_name || vm.matched_vendor_name || 'N/A'}
                        </p>
                      </div>

                      <div>
                        <span className="text-xs text-text-muted flex items-center gap-1">
                          <ShieldCheck className="w-3.5 h-3.5 text-primary" /> Vendor ID
                        </span>
                        <p className="text-sm font-mono font-semibold text-text-main mt-1">
                          {ext.vendor_id || vm.matched_vendor_id || 'Unmatched'}
                        </p>
                      </div>

                      <div>
                        <span className="text-xs text-text-muted flex items-center gap-1">
                          <Receipt className="w-3.5 h-3.5 text-primary" /> Invoice ID
                        </span>
                        <p className="text-sm font-mono font-semibold text-primary mt-1">
                          {ext.invoice_id || 'N/A'}
                        </p>
                      </div>

                      <div>
                        <span className="text-xs text-text-muted flex items-center gap-1">
                          <DollarSign className="w-3.5 h-3.5 text-primary" /> Amount
                        </span>
                        <p className="text-sm font-semibold text-text-main mt-1">
                          {ext.total_amount != null ? formatINR(ext.total_amount) : 'N/A'}
                        </p>
                      </div>

                      <div>
                        <span className="text-xs text-text-muted flex items-center gap-1">Currency</span>
                        <p className="text-sm font-mono text-text-main mt-1">{ext.currency || 'INR'}</p>
                      </div>

                      <div>
                        <span className="text-xs text-text-muted flex items-center gap-1">PO Number</span>
                        <p className="text-sm font-mono text-text-main mt-1">{ext.po_id || 'None'}</p>
                      </div>

                      <div>
                        <span className="text-xs text-text-muted flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5 text-primary" /> Invoice Date
                        </span>
                        <p className="text-sm text-text-main mt-1">{ext.invoice_date || 'N/A'}</p>
                      </div>

                      <div>
                        <span className="text-xs text-text-muted flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5 text-primary" /> Due Date
                        </span>
                        <p className="text-sm text-text-main mt-1">{ext.due_date || 'N/A'}</p>
                      </div>

                      <div>
                        <span className="text-xs text-text-muted flex items-center gap-1">
                          <CreditCard className="w-3.5 h-3.5 text-primary" /> Bank Account
                        </span>
                        <p className="text-sm font-mono text-text-main mt-1">{ext.bank_account || 'N/A'}</p>
                      </div>
                    </div>

                    {ext.validation_warnings?.length > 0 && (
                      <div className="p-3 bg-warning/10 border border-warning/30 rounded-lg text-xs text-warning space-y-1">
                        <div className="font-semibold flex items-center gap-1">
                          <AlertTriangle className="w-4 h-4 shrink-0" /> OCR Parsing Warnings:
                        </div>
                        <ul className="list-disc pl-4 space-y-0.5">
                          {ext.validation_warnings.map((w, idx) => (
                            <li key={idx}>{w}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </Card>
            </div>

            {/* Vendor Matching & Payment Creation Action Card */}
            <div className="space-y-6">
              <Card title="Vendor Master Verification">
                <div className="space-y-4">
                  <div className="p-3 bg-navy-bg/60 rounded-lg border border-navy-border space-y-2">
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-text-muted">Vendor Match Status:</span>
                      <span className="font-mono font-semibold text-primary">{vm.status || 'UNKNOWN'}</span>
                    </div>

                    <div className="flex justify-between items-center text-xs">
                      <span className="text-text-muted">Vendor Approval:</span>
                      <Badge status={vm.is_approved ? 'APPROVED' : 'HOLD'}>
                        {vm.is_approved ? 'APPROVED VENDOR' : 'UNAPPROVED VENDOR'}
                      </Badge>
                    </div>

                    <div className="flex justify-between items-center text-xs">
                      <span className="text-text-muted">Bank Account Match:</span>
                      {vm.bank_account_matches === true ? (
                        <span className="text-success font-medium flex items-center gap-1">
                          <Check className="w-3.5 h-3.5" /> Matched
                        </span>
                      ) : vm.bank_account_matches === false ? (
                        <span className="text-danger font-medium flex items-center gap-1">
                          <AlertTriangle className="w-3.5 h-3.5" /> Mismatched
                        </span>
                      ) : (
                        <span className="text-text-muted">Not Verified</span>
                      )}
                    </div>
                  </div>

                  <p className="text-xs text-text-muted leading-relaxed">
                    {vm.message || 'Verification complete. OCR extracted vendor matches registered master profile.'}
                  </p>

                  <div className="pt-2 border-t border-navy-border space-y-3">
                    <Button
                      variant="primary"
                      onClick={handleCreatePaymentRequest}
                      disabled={creatingPayment || !!createdPaymentResult}
                      className="w-full flex items-center justify-center gap-2 py-2.5"
                    >
                      {creatingPayment ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin text-navy-bg" />
                          <span>Creating Payment Request...</span>
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="w-4 h-4 text-navy-bg" />
                          <span>Create Payment Request</span>
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </Card>

              {/* Success Result Box */}
              {createdPaymentResult && (
                <Card className="border-success/40 bg-success/5 shadow-lg">
                  <div className="space-y-3 text-center">
                    <div className="w-12 h-12 rounded-full bg-success/20 border border-success/40 flex items-center justify-center mx-auto text-success">
                      <CheckCircle2 className="w-7 h-7" />
                    </div>
                    <div>
                      <h4 className="font-bold text-text-main text-base">Payment Request Created</h4>
                      <p className="text-xs text-text-muted mt-0.5">
                        Document successfully linked to TrustGuard payment pipeline.
                      </p>
                    </div>

                    <div className="p-3 bg-navy-surface rounded-lg border border-navy-border font-mono text-sm font-bold text-primary">
                      {createdPaymentResult.payment_request_id || createdPaymentResult.payment?.request_id}
                    </div>

                    <div className="pt-2 flex flex-col gap-2">
                      <Link
                        to={`/risk/${createdPaymentResult.payment_request_id || createdPaymentResult.payment?.request_id}`}
                      >
                        <Button variant="primary" className="w-full flex items-center justify-center gap-2">
                          <span>Proceed to Risk Analysis</span>
                          <ArrowRight className="w-4 h-4 text-navy-bg" />
                        </Button>
                      </Link>
                      <Link
                        to={`/payments/${createdPaymentResult.payment_request_id || createdPaymentResult.payment?.request_id}`}
                      >
                        <Button variant="secondary" className="w-full text-xs">
                          View Payment Details
                        </Button>
                      </Link>
                    </div>
                  </div>
                </Card>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
