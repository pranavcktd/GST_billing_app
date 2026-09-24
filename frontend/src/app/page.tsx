"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Loading } from "@/components/ui";
import { useAuth } from "@/lib/auth";

export default function Home() {
  const { me, loading, business } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!me) router.replace("/login");
    else router.replace(business ? "/dashboard" : "/onboarding");
  }, [me, loading, business, router]);

  return <Loading />;
}
