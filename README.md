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
# backend (Python 3.12)
cd backend
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
copy .env.example .env                              # SQLite works out of the box
alembic upgrade head
uvicorn app.main:app --reload --port 8000           # API docs: http://localhost:8000/docs
pytest                                              # 24 tests

# frontend (Node 20+)
cd frontend
npm install
echo NEXT_PUBLIC_API_URL=http://localhost:8000 > .env.local
npm run dev                                         # http://localhost:3000
```

## Deploying to Railway

1. **Database:** in your Railway project, add a **PostgreSQL** service.
2. **Backend:** add a service from this repo with root directory `backend`. `railway.json` runs `alembic upgrade head` before each deploy. Set these variables:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
   - `JWT_SECRET`: a long random string
   - `CORS_ORIGINS`: your frontend URL
   - `CLOUDINARY_URL`
   - optionally `SMTP_*` for emailed backups
3. **Frontend:** add a service with root directory `frontend` (or deploy on Vercel). Set `NEXT_PUBLIC_API_URL`.

## Roadmap
- e-Invoice (IRN + QR via IRP/GSP) and e-Way Bill.
- GSTR-1 JSON export for the portal.
- UPI QR on invoices; thermal (80mm) print.
- Multiple godowns, barcode POS mode, audit log, Tally export.
- Subscription billing (Razorpay), offline mode, React Native app.
