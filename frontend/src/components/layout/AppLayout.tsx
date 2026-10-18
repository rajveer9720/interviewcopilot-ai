import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useStore } from "../../store";
import {
  LayoutDashboard, Mic, Settings, CreditCard,
  LogOut, ChevronLeft, ChevronRight,
} from "lucide-react";
import { clsx } from "clsx";
import { apiClient } from "../../api/client";

const NavItem = ({ to, icon: Icon, label }: { to: string; icon: any; label: string }) => (
  <NavLink
    to={to}
    title={label}
    aria-label={label}
    className={({ isActive }) =>
      clsx(
        "flex items-center justify-center sm:justify-start gap-3 px-3 py-2 rounded text-sm font-medium transition-colors",
        isActive
          ? "bg-accent/15 text-accent"
          : "text-muted hover:text-primary hover:bg-surface-2"
      )
    }
  >
    <Icon size={18} />
    <span className="hidden sm:inline">{label}</span>
  </NavLink>
);

export default function AppLayout() {
  const { user, logout, sidebarOpen, toggleSidebar } = useStore();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try { await apiClient.post("/auth/logout"); } catch { /* Clear local auth even when offline. */ }
    logout();
    navigate("/login");
  };

  return (
    <div className="flex h-full bg-bg text-primary font-sans overflow-hidden">
      {/* ── Sidebar ───────────────────────────────────────── */}
      <aside
        className={clsx(
          "flex shrink-0 flex-col border-r border-border bg-surface transition-all duration-200",
          sidebarOpen ? "w-14 sm:w-56" : "w-14"
        )}
      >
        {/* Logo */}
        <div className="flex items-center gap-2 px-3 py-4 border-b border-border min-h-[56px]">
          <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center flex-shrink-0">
            <Mic size={14} className="text-white" />
          </div>
          {sidebarOpen && (
            <span className="hidden sm:block font-semibold text-sm leading-tight">
              InterviewCopilot
              <span className="block text-[10px] text-muted font-normal">AI</span>
            </span>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-2 py-3 space-y-1">
          {sidebarOpen ? (
            <>
              <NavItem to="/dashboard" icon={LayoutDashboard} label="Dashboard" />
              <NavItem to="/practice"  icon={Mic}             label="Practice" />
              <NavItem to="/settings"  icon={Settings}        label="Settings" />
              <NavItem to="/billing"   icon={CreditCard}      label="Billing" />
            </>
          ) : (
            <>
              {[
                ["/dashboard", LayoutDashboard],
                ["/practice",  Mic],
                ["/settings",  Settings],
                ["/billing",   CreditCard],
              ].map(([to, Icon]: any) => (
                <NavLink
                  key={to}
                  to={to}
                  title={String(to).slice(1)}
                  aria-label={String(to).slice(1)}
                  className={({ isActive }) =>
                    clsx(
                      "flex items-center justify-center w-10 h-10 rounded transition-colors",
                      isActive ? "bg-accent/15 text-accent" : "text-muted hover:text-primary"
                    )
                  }
                >
                  <Icon size={18} />
                </NavLink>
              ))}
            </>
          )}
        </nav>

        {/* User + Logout */}
        <div className="border-t border-border p-2 space-y-1">
          {sidebarOpen && (
            <div className="hidden sm:block min-w-0 px-3 py-2">
              <p className="text-xs text-primary truncate">{user?.email}</p>
              <span className="text-[10px] text-accent uppercase tracking-wider font-medium">
                {user?.plan_tier}
              </span>
            </div>
          )}
          <button
            title="Sign out"
            aria-label="Sign out"
            onClick={handleLogout}
            className="flex items-center gap-3 w-full px-3 py-2 rounded text-sm text-muted hover:text-error hover:bg-error/10 transition-colors"
          >
            <LogOut size={18} />
            {sidebarOpen && <span className="hidden sm:inline">Sign out</span>}
          </button>
        </div>

        {/* Toggle */}
        <button
          aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
          onClick={toggleSidebar}
          className="hidden sm:flex items-center justify-center h-8 border-t border-border text-muted hover:text-primary transition-colors"
        >
          {sidebarOpen ? <ChevronLeft size={14} /> : <ChevronRight size={14} />}
        </button>
      </aside>

      {/* ── Main Content ──────────────────────────────────── */}
      <main className="min-w-0 flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
