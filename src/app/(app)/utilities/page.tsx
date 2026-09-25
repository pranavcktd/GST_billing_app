import { Building2, Calculator, DatabaseBackup, FileSpreadsheet, FileUp, History, Percent, Tags } from "lucide-react";
import Link from "next/link";

const TOOLS = [
  { href: "/utilities/companies", title: "Manage companies", desc: "Switch, create or delete companies; add staff and your CA with roles", icon: Building2 },
  { href: "/utilities/backup", title: "Backup & restore", desc: "Automatic daily backup, download to phone/PC, email backup, restore", icon: DatabaseBackup },
  { href: "/utilities/import", title: "Import data", desc: "Bulk import invoices, purchases, parties, items, stock, payments, expenses", icon: FileUp },
  { href: "/utilities/hsn", title: "HSN / SAC master", desc: "Import, update or delete HSN/SAC codes with current GST rates", icon: Tags },
  { href: "/utilities/tax-slab", title: "Update tax slab", desc: "Change GST rate on many items at once after a rate change", icon: Percent },
  { href: "/utilities/gst-calculator", title: "GST calculator", desc: "Add or remove GST, split into CGST / SGST / IGST", icon: Calculator },
  { href: "/utilities/tally", title: "Export to Tally", desc: "Ledgers and vouchers as Tally XML for your CA", icon: FileSpreadsheet },
  { href: "/utilities/audit", title: "Audit trail", desc: "Who created, changed or deleted what — and when", icon: History },
];

export default function UtilitiesPage() {
  return (
    <>
      <h1 className="mb-5 text-xl font-semibold text-gray-900">Important utilities</h1>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {TOOLS.map(({ href, title, desc, icon: Icon }) => (
          <Link key={href} href={href} className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-colors hover:border-brand-500">
            <Icon className="mb-3 text-brand-600" size={22} />
            <div className="font-semibold text-gray-900">{title}</div>
            <p className="mt-1 text-sm text-gray-500">{desc}</p>
          </Link>
        ))}
      </div>
    </>
  );
}
