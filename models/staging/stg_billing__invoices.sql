select invoice_id, account_id, invoice_amount, invoice_date, loaded_at
from {{ ref('billing_invoices') }}
