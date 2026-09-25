"""Report catalogue: category, title, filters and the function that builds each report.

Filters: period | as_of | party | party* | item* | account | loan* | expense_category  (* = required)
"""

from . import gst, items, misc, party, transaction

R = lambda slug, category, title, desc, filters, fn=None, href=None: dict(  # noqa: E731
    slug=slug, category=category, title=title, description=desc, filters=filters, fn=fn, href=href)

TXN, PARTY, GST, ITEM, BIZ, TAX, EXP, ORD, LOAN = (
    "Transaction", "Party", "GST", "Item / Stock", "Business status", "Taxes", "Expense",
    "Sale / Purchase orders", "Loan")

CATALOG = [
    R("sale", TXN, "Sale report", "Sale invoices & credit notes with tax columns", ["period", "party"], transaction.sale_register),
    R("purchase", TXN, "Purchase report", "Purchase bills & debit notes with tax columns", ["period", "party"], transaction.purchase_register),
    R("day-book", TXN, "Day book / all transactions", "Every document and money movement", ["period"], transaction.day_book),
    R("payments", TXN, "Payment report", "Payments received and made", ["period", "party"], transaction.payment_register),
    R("bill-profit", TXN, "Bill wise profit", "Profit and margin on every sale bill", ["period", "party"], transaction.bill_wise_profit),
    R("profit-loss", TXN, "Profit & loss", "Trading and P&L account", ["period"], transaction.profit_loss),
    R("sale-aging", TXN, "Sale aging", "Receivables by age bucket", ["as_of"], transaction.sale_aging),
    R("purchase-aging", TXN, "Purchase aging", "Payables by age bucket", ["as_of"], transaction.purchase_aging),
    R("cash-flow", TXN, "Cash flow", "Money in and out of cash & bank by activity", ["period"], transaction.cash_flow),
    R("balance-sheet", TXN, "Balance sheet", "Assets, liabilities and capital", ["as_of"], transaction.balance_sheet_report),
    R("capital", TXN, "Capital account", "Opening capital, introduced, drawings, profit", ["period"], transaction.capital_account),

    R("party-statement", PARTY, "Party statement", "Ledger of one party with running balance", ["period", "party*"], party.party_statement),
    R("party-ledger", PARTY, "Party ledger (all parties)", "Opening, debit, credit, closing for every party", ["period"], party.party_ledger_summary),
    R("party-pnl", PARTY, "Party wise profit & loss", "Sales, cost and profit per customer", ["period"], party.party_pnl),
    R("all-parties", PARTY, "All parties", "Contact, GSTIN and balance of every party", [], party.all_parties),
    R("party-by-item", PARTY, "Party report by item", "What a party bought / supplied, item wise", ["period", "party*"], party.party_by_item),
    R("sale-purchase-by-party", PARTY, "Sale / purchase by party", "Totals per party", ["period"], party.sale_purchase_by_party),

    R("gstr1", GST, "GSTR-1", "Outward supplies: B2B, B2CL, B2CS, CDNR, HSN, documents", ["period"], href="/reports/gstr1"),
    R("gstr2", GST, "GSTR-2", "Inward supplies with ITC, to reconcile with GSTR-2B", ["period"], gst.gstr2),
    R("gstr3b", GST, "GSTR-3B", "Monthly summary: liability, ITC, net payable", ["period"], href="/reports/gstr3b"),
    R("cmp08", GST, "CMP-08", "Composition dealer quarterly statement", ["period"], gst.cmp08),
    R("gstr4", GST, "GSTR-4", "Composition dealer annual return", ["period"], gst.gstr4),
    R("gst-transactions", GST, "GSTR transaction report", "All GST documents with tax breakup", ["period"], gst.gst_transactions),
    R("gstr9", GST, "GSTR-9", "Annual return summary with HSN tables", ["period"], gst.gstr9),
    R("hsn-sales", GST, "Sale summary by HSN", "HSN-wise outward supplies", ["period"], gst.hsn_sales),
    R("hsn-purchases", GST, "Purchase summary by HSN", "HSN-wise inward supplies", ["period"], gst.hsn_purchases),
    R("sac", GST, "SAC report", "Services (SAC 99xx) summary", ["period"], gst.sac_report),

    R("stock-summary", ITEM, "Stock summary", "Opening, in, out, closing and value", ["period"], items.stock_summary),
    R("stock-details", ITEM, "Stock details", "Movement of each item by type", ["period"], items.stock_details),
    R("item-pnl", ITEM, "Item wise profit & loss", "Sales, cost and profit per item", ["period"], items.item_pnl),
    R("item-by-party", ITEM, "Item report by party", "Who bought / supplied an item", ["period", "item*"], items.item_by_party),
    R("item-details", ITEM, "Item details", "Day-wise movement of one item", ["period", "item*"], items.item_details),
    R("godown-stock", ITEM, "Stock by godown", "Quantity of every item in each godown", ["as_of"], items.godown_stock),
    R("low-stock", ITEM, "Low stock summary", "Items at or below minimum level", ["as_of"], items.low_stock),
    R("category-sales", ITEM, "Sale / purchase by item category", "Totals per item category", ["period"], items.sale_purchase_by_category),
    R("category-stock", ITEM, "Stock summary by item category", "Quantity and value per category", ["as_of"], items.stock_by_category),
    R("batch", ITEM, "Item batch report", "Stock by batch with expiry", ["as_of"], items.batch_report),
    R("serial", ITEM, "Item serial report", "Serial numbers in stock and sold", ["as_of"], items.serial_report),
    R("item-discount", ITEM, "Item wise discount", "Discount given per item", ["period"], items.item_discount),

    R("bank-statement", BIZ, "Bank / cash statement", "Statement of a cash or bank account", ["period", "account"], misc.bank_statement),
    R("discount", BIZ, "Discount report", "Bill-wise discount given and received", ["period"], misc.discount_report),

    R("gst-report", TAX, "GST report", "Month-wise output tax, ITC and net payable", ["period"], gst.gst_summary),
    R("gst-rate", TAX, "GST rate report", "Sales and purchases by GST rate", ["period"], gst.gst_rate_report),
    R("form-27eq", TAX, "Form No. 27EQ", "TCS collected on sales (quarterly return)", ["period"], misc.form_27eq),
    R("tcs-receivable", TAX, "TCS receivable", "TCS charged by your suppliers", ["period"], misc.tcs_receivable),
    R("tds-payable", TAX, "TDS payable", "TDS you deducted on payments", ["period"], misc.tds_payable),
    R("tds-receivable", TAX, "TDS receivable", "TDS deducted by your customers", ["period"], misc.tds_receivable),
    R("tax-payments", TAX, "Tax payments", "GST / TDS / TCS challans paid", ["period"], misc.tax_payments),

    R("expense-transactions", EXP, "Expense transaction report", "Every expense with GST and payment", ["period", "expense_category", "party"], misc.expense_transactions),
    R("expense-category", EXP, "Expense category report", "Totals per category", ["period"], misc.expense_category_report),
    R("expense-item", EXP, "Expense item report", "Totals per expense item", ["period", "expense_category"], misc.expense_item_report),

    R("sale-orders", ORD, "Sale order report", "Sale orders with status", ["period", "party"], misc.sale_orders),
    R("purchase-orders", ORD, "Purchase order report", "Purchase orders with status", ["period", "party"], misc.purchase_orders),
    R("delivery-challans", ORD, "Delivery challan report", "Challans pending invoicing", ["period", "party"], misc.delivery_challans),
    R("estimates", ORD, "Estimate report", "Quotations and conversion status", ["period", "party"], misc.estimates),
    R("pending-order-items", ORD, "Pending order items", "Quantities still to deliver / receive", ["as_of"], misc.pending_order_items),

    R("loan-statement", LOAN, "Loan statement", "Disbursements, EMIs and outstanding", ["period", "loan*"], misc.loan_statement),
    R("loans", LOAN, "Loan accounts", "Outstanding and interest per loan", ["period"], misc.loan_summary),
]

BY_SLUG = {r["slug"]: r for r in CATALOG}
