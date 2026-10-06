import { API_BASE } from './riskApi';

/**
 * Upload invoice PDF/image document for OCR extraction
 * POST /invoices/upload (multipart/form-data)
 */
export async function uploadInvoice(file, uploaderId = 'emp_accounts_01') {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('uploader_id', uploaderId);

  const response = await fetch(`${API_BASE}/invoices/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Invoice upload failed with status ${response.status}`);
  }

  return await response.json();
}

/**
 * Review/edit invoice OCR values before payment request creation
 * POST /invoices/{document_id}/review
 */
export async function reviewInvoice(documentId, reviewData) {
  const response = await fetch(`${API_BASE}/invoices/${documentId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(reviewData),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Invoice review failed with status ${response.status}`);
  }

  return await response.json();
}

/**
 * Create Payment Request from extracted invoice document
 * POST /invoices/{document_id}/create-payment-request
 */
export async function createPaymentFromInvoice(documentId, confirmation = null) {
  const options = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  };
  
  if (confirmation) {
    options.body = JSON.stringify(confirmation);
  } else {
    options.body = JSON.stringify(null);
  }

  const response = await fetch(`${API_BASE}/invoices/${documentId}/create-payment-request`, options);

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    let errorMessage = `Payment request creation failed with status ${response.status}`;
    if (errorBody.detail) {
      errorMessage = typeof errorBody.detail === 'string' ? errorBody.detail : JSON.stringify(errorBody.detail);
    }
    throw new Error(errorMessage);
  }

  return await response.json();
}

/**
 * Fetch invoice document status and OCR data
 * GET /invoices/{document_id}
 */
export async function getInvoiceDocument(documentId) {
  const response = await fetch(`${API_BASE}/invoices/${documentId}`);
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Fetch invoice failed with status ${response.status}`);
  }
  return await response.json();
}
