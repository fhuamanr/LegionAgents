import Link from "next/link";
import type { ReactNode } from "react";
import { Activity, BookOpenText, Bug, GitPullRequest, LayoutDashboard, RadioTower, UserCheck } from "lucide-react";
import { Button } from "@/components/ui/button";

interface NavItem {
  readonly href: string;
  readonly label: string;
  readonly icon: typeof LayoutDashboard;
}

const navItems: readonly NavItem[] = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/executions", label: "Executions", icon: Activity },
  { href: "/dashboard/qa", label: "QA Reports", icon: Bug },
  { href: "/dashboard/approvals", label: "Approvals", icon: UserCheck },
  { href: "/dashboard/docs", label: "Docs", icon: BookOpenText },
  { href: "/dashboard/pr", label: "PR", icon: GitPullRequest },
];

export function AppShell({ children }: Readonly<{ children: ReactNode }>): JSX.Element {
  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r bg-card lg:block">
        <div className="flex h-16 items-center gap-3 border-b px-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <RadioTower className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <div className="text-sm font-semibold">AgentOps</div>
            <div className="text-xs text-muted-foreground">Delivery control plane</div>
          </div>
        </div>
        <nav className="space-y-1 p-3">
          {navItems.map((item) => (
            <Button key={item.href} asChild variant="ghost" className="w-full justify-start">
              <Link href={item.href as never}>
                <item.icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </Link>
            </Button>
          ))}
        </nav>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b bg-background/90 px-4 backdrop-blur md:px-6">
          <div>
            <h1 className="text-base font-semibold">Multi-Agent Delivery Dashboard</h1>
            <p className="text-xs text-muted-foreground">Workflow execution, QA evidence, documentation, and PR readiness</p>
          </div>
          <div className="hidden items-center gap-2 md:flex">
            <BadgeDot />
            <span className="text-xs text-muted-foreground">WebSocket-ready</span>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}

function BadgeDot(): JSX.Element {
  return <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_0_4px_rgba(52,211,153,0.16)]" />;
}
