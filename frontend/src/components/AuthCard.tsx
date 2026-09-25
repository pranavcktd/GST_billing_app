import { BrandLogo } from "@/components/BrandLogo";

export function AuthCard({ title, sub, children }: { title: string; sub: string; children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6"><BrandLogo size="lg" /></div>
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm sm:p-8">
          <h1 className="text-xl font-semibold text-gray-900">{title}</h1>
          <p className="mt-1 mb-6 text-sm text-gray-500">{sub}</p>
          {children}
        </div>
      </div>
    </div>
  );
}
