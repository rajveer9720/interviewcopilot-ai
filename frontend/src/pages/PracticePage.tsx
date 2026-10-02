import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useStore } from "../store";
import { apiClient } from "../api/client";
import { Mic, Briefcase, Building2, FileText, ChevronRight } from "lucide-react";
import toast from "react-hot-toast";
import { clsx } from "clsx";

const schema = z.object({
  mode:           z.enum(["practice", "interview", "review"]),
  title:          z.string().optional(),
  target_role:    z.string().optional(),
  target_company: z.string().optional(),
  resume_id:      z.string().optional(),
});

type FormData = z.infer<typeof schema>;

const MODES = [
  {
    id:   "practice",
    name: "Practice Mode",
    desc: "Relaxed practice — verbose AI coaching & full analytics",
    icon: Mic,
  },
  {
    id:   "interview",
    name: "Interview Mode",
    desc: "Real interview feel — compact overlay, minimal distractions",
    icon: Briefcase,
  },
  {
    id:   "review",
    name: "Review Mode",
    desc: "Review past answers and get detailed improvement tips",
    icon: FileText,
  },
];

export default function PracticePage() {
  const navigate = useNavigate();
  const { startSession } = useStore();
  const [selectedMode, setSelectedMode] = useState<"practice" | "interview" | "review">("practice");
  const [loading, setLoading] = useState(false);

  const { register, handleSubmit } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { mode: "practice" },
  });

  const onSubmit = async (data: FormData) => {
    setLoading(true);
    try {
      await startSession({ ...data, mode: selectedMode });
      const latest = useStore.getState().session!;
      toast.success("Session started!");
      navigate(`/session/${latest.id}`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to start session");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-primary">Start a Session</h1>
        <p className="text-sm text-muted mt-1">
          Choose a mode, configure your session, then start practicing.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Mode Selection */}
        <div>
          <label className="text-xs text-muted uppercase tracking-wider mb-3 block">
            Session Mode
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {MODES.map(({ id, name, desc, icon: Icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => setSelectedMode(id as any)}
                className={clsx(
                  "text-left p-3 rounded-lg border transition-colors",
                  selectedMode === id
                    ? "border-accent bg-accent/10"
                    : "border-border bg-surface hover:border-accent/50"
                )}
              >
                <Icon size={18} className={selectedMode === id ? "text-accent" : "text-muted"} />
                <p className="text-sm font-medium text-primary mt-2">{name}</p>
                <p className="text-xs text-muted mt-1">{desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Session Details */}
        <div className="bg-surface border border-border rounded-lg p-4 space-y-4">
          <h2 className="text-sm font-medium text-primary">Session Details</h2>

          <div>
            <label className="text-xs text-muted block mb-1">Session Title (optional)</label>
            <input
              {...register("title")}
              placeholder="e.g., Meta Onsite Prep"
              className="w-full bg-surface-2 border border-border rounded px-3 py-2 text-sm text-primary placeholder:text-muted focus:outline-none focus:border-accent"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted block mb-1 flex items-center gap-1">
                <Briefcase size={12} /> Target Role
              </label>
              <input
                {...register("target_role")}
                placeholder="Senior Engineer"
                className="w-full bg-surface-2 border border-border rounded px-3 py-2 text-sm text-primary placeholder:text-muted focus:outline-none focus:border-accent"
              />
            </div>
            <div>
              <label className="text-xs text-muted block mb-1 flex items-center gap-1">
                <Building2 size={12} /> Company
              </label>
              <input
                {...register("target_company")}
                placeholder="Stripe, Google..."
                className="w-full bg-surface-2 border border-border rounded px-3 py-2 text-sm text-primary placeholder:text-muted focus:outline-none focus:border-accent"
              />
            </div>
          </div>
        </div>

        {/* Start Button */}
        <button
          type="submit"
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 bg-accent hover:bg-accent-hover text-white font-medium py-3 rounded-lg transition-colors disabled:opacity-50"
        >
          {loading ? (
            <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
          ) : (
            <>
              <Mic size={18} />
              Start Session
              <ChevronRight size={16} />
            </>
          )}
        </button>
      </form>
    </div>
  );
}
