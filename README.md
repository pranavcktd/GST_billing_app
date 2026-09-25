# GST Billing

GST billing, inventory and accounting SaaS for small and medium Indian businesses, for both GST-registered (regular or composition) and unregistered businesses.

| Layer | Tech |
|---|---|
| Frontend | Next.js 16 (App Router) + TypeScript + Tailwind CSS v4, installable PWA |
| Backend | FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 |
| Database | PostgreSQL (Railway); SQLite for local development/tests |
| Storage | Cloudinary (logo, signature, item images) |

## Modules

**Sales**
- Documents: sale invoice (Tax Invoice or Bill of Supply), estimate/quotation, sale order, delivery challan, payment in and credit note.
- Estimates, orders and challans convert into invoices; the source document is marked as converted.
- A delivery challan does not move stock; stock moves when the challan is invoiced.

**Purchases**
- Purchase bill, purchase order (converts into a bill), payment out and debit note.
- Reverse charge and TCS charged by suppliers.

**Expenses**
- Categories are owner-defined and marked **direct** (goes into cost of goods, e.g. manufacturing, freight inward, wages) or **indirect** (P&L operating expense, e.g. rent, salary, petrol, tea).
- Expense items belong to a category and are created automatically while typing.
- GST bills with input tax credit, and payment against a supplier or paid on the spot.

**Cash & Bank**
- Cash in hand, multiple bank accounts, transfers (deposits, withdrawals, bank to bank) and account statements.
- Cheques: open, cleared or bounced. Party dues are settled immediately, the bank balance updates on clearance, and a bounced cheque reverses the payment.
- Loan accounts: disbursements, EMIs (principal and interest) and charges.
- Capital introduced and drawings.
- GST/TDS/TCS challan payments.
- TDS on payments (receivable/payable) and TCS on bills (Sec. 206C).

**Masters**
- Parties: GSTIN checksum, opening balances, ledger, WhatsApp reminders.
- Items: HSN/SAC, UQC units, batch/expiry and serial tracking, low-stock alerts, stock adjustments.

**Reports** (55, in 9 categories, each with CSV export and print/PDF)
- *Transaction:* sale/purchase, day book, payments, bill-wise profit, P&L, sale & purchase aging, cash flow, balance sheet, capital account.
- *Party:* statement, all-party ledger, party P&L, all parties, party by item, sale/purchase by party, outstanding.
- *GST:* GSTR-1, GSTR-2, GSTR-3B, GSTR transaction report, GSTR-9, HSN sale & purchase summary, SAC report.
- *Item/Stock:* stock summary & details, item P&L, item by party, item details, low stock, sale/purchase & stock by category, batch, serial, item-wise discount.
- *Business status:* bank/cash statement, discount report.
- *Taxes:* GST report, GST rate report, Form 27EQ, TCS receivable, TDS payable/receivable, tax payments.
- *Expense:* transactions, by category, by item.
- *Orders:* sale orders, purchase orders, delivery challans, estimates, pending order items.
- *Loan:* statement, accounts.

**Dashboard**
- Sales, purchases, receipts, receivable and payable.
- Cash & bank balances and open cheques.
- Inventory summary: value at cost and at sale price, low/out of stock.
- Expenses this month by category.
- Six-month sales/purchases/expenses chart.

**Compliance & integrations**
- **e-Invoice (IRN) and e-Way bill.** NIC schema v1.1 JSON for the portal or its bulk upload. Generation runs through a switchable provider: `sandbox` for local testing, or `gsp` (add your GSP's API in `backend/app/services/einvoice.py`). IRN cancellation is allowed within 24 hours. Transport details (vehicle, LR, distance, ship-to) are printed on the bill.
- **GSTR-1 JSON** for the portal (B2B, B2CL, B2CS, CDNR/CDNUR, nil-rated, HSN B2B/B2C, documents issued) and **GSTR-2B reconciliation** (matched, mismatched, missing in books, not in 2B).
- **Tally XML export** of ledgers and balanced vouchers.

**Printing & POS**
- Invoice themes (classic, modern, minimal), accent colour, A4/A5 and thermal 80/58 mm, and Original/Duplicate/Triplicate copies.
- Custom fields, a UPI "scan to pay" QR, and the e-invoice signed QR.
- POS counter with barcode scanning (F9 saves and prints). Barcode label sheets with auto-generated in-store EAN-13 codes.

**Multi-location:** godowns with stock transfers, a stock-by-godown report, and a godown chosen on each bill.

**Subscription tiers** (per account, covering all of the owner's businesses; edit `backend/app/services/plans.py`)

| | Free | Starter | Professional | Enterprise |
|---|---|---|---|---|
| Invoices | 30/month, 300/year | 250/month | Unlimited | Unlimited |
| Businesses | 1 | 1 | 3 | 10 + add-on packs |
| Users | 1 | 2 | 5 | Unlimited |
| e-Invoice / e-Way bill | — | JSON | Direct API (500/month) | Direct API (5000/month) |
| Reports | Day book, sales and basic | + P&L, balance sheet, inventory, GST | + ledgers, audit trail, 2B matching, profit reports | + batch/serial, godown stock |
| Branding | Watermark | No watermark | Custom themes and logo | + barcode labels, custom roles |
| Cloud backup | 100 MB | 1 GB | 5 GB | 20 GB |

- New accounts get a 14-day Enterprise trial.
- Hitting a limit shows an in-app upgrade prompt. Payment is through Razorpay (UPI, card, net banking), with signature and webhook verification.
- With `APP_ENV=development` and no Razorpay keys, payments are simulated.

**Roles**
- **Platform:** a **Super Admin** (emails listed in `SUPERADMIN_EMAILS`) gets the `/admin` console: KPIs, accounts, plan and feature-flag overrides, resellers, payouts and system health.
- **Resellers** get `/reseller`: register owners, issue licence packs, see commission. They never see business data.
- **Staff roles:** Owner, Business admin, Store manager, Billing operator, Inventory manager, Accountant/CA (read-only). Each role is a matrix of modules × view/create/edit/delete/export, plus the `view_cost` and `edit_past` flags. Custom per-person matrices are an Enterprise feature.
- **Approval PIN:** staff without `edit_past` need a manager's approval PIN to change older entries.
- **Audit trail:** every change is logged automatically.

**Super Admin console** (`/admin`)
- **Users at every level:** super admin, reseller, account owner, staff. You can create, edit, reset passwords (e-mail link or temporary password), lock/unlock, reset two-factor, activate/deactivate, sign out everywhere, change platform role, and delete.
  - Deletion is guarded: you cannot delete yourself or the last super admin, and an owner's businesses are backed up before deletion.
- **Hierarchy tree:** super admins → resellers → accounts → businesses → staff. Businesses can be transferred to a new owner.
- **Platform audit trail:** sign-ins, failed sign-ins and lockouts, and every admin or reseller action, plus every business's audit trail. Exportable to CSV.
- **Backups:** full platform, one account, or one business. All can be downloaded, imported and restored.
  - Account and business backups restore as new businesses.
  - A full backup replaces everything, after a typed confirmation and an automatic safety backup; the acting super admin keeps access.
  - A daily automatic full backup keeps the last 7.
- **Email (SMTP) per level:** platform (password resets and new-account mails), reseller, and business (invoices and backups). Each level falls back to the one above.

**Sign-in security**
- Forgot/reset password by e-mail link (one-time, 30 minutes).
- Accounts lock for 15 minutes after 5 wrong passwords.
- Optional two-factor sign-in (Google or Microsoft Authenticator).
- Temporary passwords must be changed at first sign-in.
- Changing a password or choosing "sign out everywhere" ends all other sessions immediately.
- Security headers on every response.

**Sharing:** e-mail an invoice to the customer, or share a public view link (also added to WhatsApp messages) that shows the document without a login. Links can be revoked.

**Public pages:** Terms, Privacy, Refund and Contact templates, which Razorpay needs before it activates payments. Have them reviewed before going live.

**Utilities**
- **Bulk import** for parties, items (add or update), stock, HSN/SAC, expense items, every document type (sales, estimates, orders, challans, credit/debit notes, purchases, expenses) and payments.
  - Each has an Excel template with an instructions sheet.
  - Files are checked in full before saving: either every row is saved or none is.
  - Missing parties and items are created automatically.
- **Backup & restore:**
  - Daily automatic backups (last 7 kept), manual backup, download or share to phone, email backup.
  - Restore always creates a **new** company, so live data is never overwritten.
- **Manage companies:** several companies per login; members with roles Owner, Admin, Staff or Accountant (read-only, for your CA); delete a company.
- **HSN/SAC master:** import, update or delete codes with GST rates; item forms look up the rate; rate changes can be pushed to all items.
- **Tax slab update:** change GST on many items by current rate, HSN prefix or category, with a preview first.
- **GST calculator.**

### Accounting model
Each document implies a balanced double entry, and the balance sheet is built from those entries:
- Stock is valued at weighted-average cost, with the same figure in P&L and the balance sheet.
- GST input credit is counted only when it is claimable. Otherwise the GST becomes part of the cost.
- Opening balances of accounts, parties, stock and loans form the opening capital.

The test suite checks that the balance sheet balances exactly across a month of mixed activity. If it ever did not, a "Difference" line would appear.

## Local development

```bash
# database: PostgreSQL 17 in Docker (same engine as production)
docker run -d --name gst-billing-db -e POSTGRES_USER=gst -e POSTGRES_PASSWORD=<pw> -e POSTGRES_DB=gst_billing   -p 5433:5432 -v gst_billing_pg:/var/lib/postgresql/data postgres:17-alpine
#   .env: DATABASE_URL=postgresql://gst:<pw>@localhost:5433/gst_billing
#         TEST_DATABASE_URL=postgresql://gst:<pw>@localhost:5433/gst_billing_test

# backend (Python 3.12)
cd backend
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
copy .env.example .env                              # SQLite works out of the box
alembic upgrade head                                # incremental migrations — existing data is kept
uvicorn app.main:app --reload --port 8000           # API docs: http://localhost:8000/docs
pytest                                              # 44 tests (uses TEST_DATABASE_URL if set)

# frontend (Node 20+)
cd frontend
npm install
npm run dev                                         # http://localhost:3000
# /api is proxied by Next.js to the backend (next.config.ts), so other PCs on the network can use
# http://<this-pc-ip>:3000 — only port 3000 needs to be reachable; the API stays on 127.0.0.1.
```

## Deploying to Railway

1. **Database:** in your Railway project, add a **PostgreSQL** service.
2. **Backend:** add a service from this repo with root directory `backend`. `railway.json` runs `alembic upgrade head` before each deploy. Set these variables:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
   - `JWT_SECRET`: a long random string
   - `CORS_ORIGINS`: your frontend URL
   - `CLOUDINARY_URL`
   - `APP_ENV=production`, `SUPERADMIN_EMAILS` and `APP_URL` (the public web address used in e-mailed links)
   - `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET` (webhook URL `/api/billing/webhook`, events `payment.captured` and `order.paid`)
   - `EINVOICE_PROVIDER` plus the `GSP_*` settings once you have a GSP
   - optionally `SMTP_*` for emailed backups
3. **Frontend:** add a service with root directory `frontend` (or deploy on Vercel). Set `API_PROXY_TARGET` to the backend's URL (the browser calls `/api` on the frontend's own domain, so no CORS setup is needed).

## Roadmap
- Plug in a GSP's API for live IRN and e-way bill generation (the adapter is ready).
- SMS/WhatsApp gateway (OTP approvals, invoice sending).
- Offline mode and a React Native app.
