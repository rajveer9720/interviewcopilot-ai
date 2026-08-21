import { useEffect, useState } from "react";
import { useStore } from "../store";
import { apiClient } from "../api/client";
import { Check, Zap, ExternalLink } from "lucide-react";
import { clsx } from "clsx";
import toast from "react-hot-toast";

interface Plan {
  id: string; name: string; price_usd: number; razorpay_plan_id?: string;
  sessions_per_month: number | null; max_duration_mins: number;
  llm_providers: string[]; features: string[];
}

declare global {
  interface Window {
    Razorpay: new (options: Record<string, unknown>) => { open: () => void };
  }
}

export default function BillingPage() {
  const { user } = useStore();
  const [plans, setPlans] = useState<Plan[]>([]);

  useEffect(() => {
    apiClient.get("/billing/plans").then((r) => setPlans(r.data));
  }, []);

  const handleCheckout = async (plan: Plan) => {
    if (!plan.razorpay_plan_id || !window.Razorpay) return;
    try {
      const { data } = await apiClient.post("/billing/checkout", null, {
        params: { plan_id: plan.razorpay_plan_id },
      });
      const checkout = new window.Razorpay({
        key: data.key_id,
        subscription_id: data.subscription_id,
        name: data.name,
        description: `${plan.name} subscription`,
        prefill: { name: user?.full_name || "", email: data.email },
        theme: { color: "#7C5CFC" },
        handler: () => toast.success("Payment received. Your plan will update shortly."),
      });
      checkout.open();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Checkout failed");
    }
  };

  const currentTier = user?.plan_tier || "free";

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-primary">Billing & Plans</h1>
        <p className="text-sm text-muted mt-1">
          Current plan: <span className="text-accent capitalize font-medium">{currentTier}</span>
          {" · "}
          <span className="text-muted text-xs inline-flex items-center gap-1">
            Manage billing in Razorpay <ExternalLink size={10} />
          </span>
        </p>
      </div>

      {/* 7-day trial banner */}
      {currentTier === "free" && (
        <div className="bg-accent/10 border border-accent/20 rounded-lg p-4 mb-6">
          <p className="text-sm text-primary font-medium">🎁 7-day free trial on Pro</p>
          <p className="text-xs text-muted mt-1">Try all Pro features — no charge until your trial ends.</p>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {plans.map((plan) => {
          const isCurrentPlan = currentTier === plan.id;
          const isPopular     = plan.id === "pro";

          return (
            <div
              key={plan.id}
              className={clsx(
                "relative bg-surface border rounded-lg p-5 flex flex-col",
                isPopular ? "border-accent shadow-glow" : "border-border"
              )}
            >
              {isPopular && (
                <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 bg-accent text-white text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider">
                  Most Popular
                </span>
              )}

              <div className="mb-4">
                <p className="text-sm font-semibold text-primary">{plan.name}</p>
                <div className="flex items-end gap-1 mt-1">
                  <span className="text-2xl font-bold text-primary">${plan.price_usd}</span>
                  <span className="text-xs text-muted mb-0.5">/month</span>
                </div>
              </div>

              <ul className="space-y-2 flex-1 mb-5">
                {plan.features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-primary">
                    <Check size={12} className="text-success mt-0.5 flex-shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>

              <button
                onClick={() => handleCheckout(plan)}
                disabled={isCurrentPlan || plan.id === "free"}
                className={clsx(
                  "w-full py-2 rounded text-sm font-medium transition-colors flex items-center justify-center gap-1",
                  isCurrentPlan
                    ? "bg-surface-2 text-muted cursor-default"
                    : plan.id === "free"
                    ? "bg-surface-2 text-muted cursor-default"
                    : "bg-accent hover:bg-accent-hover text-white"
                )}
              >
                {isCurrentPlan ? "Current Plan" : plan.id === "free" ? "Free Forever" : (
                  <><Zap size={13} /> Upgrade</>
                )}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
