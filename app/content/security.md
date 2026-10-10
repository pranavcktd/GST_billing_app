> How {{brand}} protects your data, how long data is kept, and what the platform does for the record-keeping rules of the GST law and the Companies Act. This page describes measures that are in place today.

## 1. Protecting access

- All traffic to the Service uses encrypted HTTPS (TLS) connections.
- Passwords are stored only as one-way hashes (bcrypt). Accounts lock for 15 minutes after repeated wrong passwords.
- Optional two-factor sign-in with an authenticator app; sign-in with a one-time code on WhatsApp or e-mail; “sign out everywhere”.
- Role-based permissions for staff, staff sign-in controls (devices, places and hours chosen by the owner), and a manager approval PIN for changes to older entries.
- API keys, portal passwords and digital signature certificates are encrypted in the database with an application key and are never sent back to browsers.

## 2. Records the law requires

- **No deletion of issued documents** — tax invoices and notes can only be cancelled or corrected by a credit / debit note; cancelled numbers stay in the series (CGST Rules 46, 53).
- **Audit trail (edit log)** — every change to books of account is recorded with the values before and after, the user, the time and the IP address. It cannot be switched off, and the database itself refuses any change or deletion of it (Companies (Accounts) Rules 3(1)).
- **HSN/SAC on invoices** — required on B2B invoices and notes (4 digits up to ₹5 crore turnover, 6 above, and also on B2C above ₹5 crore).
- **“Clear data”** — only for test entries; blocked once documents are reported to the government or returns are filed; a backup is kept before anything is cleared.

## 3. Backups and hosting

- Automatic daily backups of each business (the latest 7 are kept), manual backups whenever you want, and a full platform backup every day.
- You can download any backup, or an Excel copy of your data, at any time — and restore it.
- {{#if legal.data_location}}Database and backups are hosted in **{{legal.data_location}}**. {{/if}}Companies must keep a backup of their books on servers in India (Companies (Accounts) Rules 3(5)); please also keep your own copies.

## 4. Retention schedule

| Data | Retention |
|---|---|
| Invoices, notes, books of account, audit trail | At least 72 months from the annual-return due date (CGST s.36) / 8 financial years (Companies Act s.128) |
| Backups taken before data was cleared | Kept; cannot be deleted by users |
| Daily automatic backups | Rolling — latest 7 |
| One-time codes | Expire in 5–10 minutes; only a keyed hash is stored |
| Account data after closure | Deleted within 90 days, except records required by law |

## 5. Incidents

We keep a register of security incidents. If an incident affects your data we notify the account owner by e-mail without undue delay so that you can meet your own duties under the DPDP Act. To report a vulnerability, write to {{legal.grievance_email}} — please do not test the Service without our written permission.

## 6. More

See the [Privacy Policy](/privacy) and the [Data Processing Addendum](/dpa).
