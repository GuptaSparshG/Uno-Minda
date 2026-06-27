import type { ReactNode } from "react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

export default function Layout({
  title,
  subtitle,
  right,
  children,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 min-w-0">
        <div className="px-7 py-6">
          <TopBar title={title} subtitle={subtitle} right={right} />
          <div className="mt-5">{children}</div>
        </div>
      </main>
    </div>
  );
}
