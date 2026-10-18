import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useStore } from "../store";
import { Mic, Briefcase, Building2, FileText, ChevronRight, Check, Headphones, ArrowRight, Loader2 } from "lucide-react";
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
    desc: "Answer AI interview questions and get personal feedback.",
    icon: Mic,
    detail: "An AI interviewer asks one question at a time. Type or record your answer, get feedback, and continue with a relevant follow-up. Submitted progress is saved.",
  },
  {
    id:   "interview",
    name: "Interview Mode",
    desc: "Listen to interview questions and keep sample answers nearby.",
    icon: Briefcase,
    detail: "Capture meeting audio in the Windows app and read suggested answers. The desktop app also supports a compact overlay for a smaller answer view.",
  },
  {
    id:   "review",
    name: "Review Mode",
    desc: "Start a session to revisit questions with AI sample answers.",
    icon: FileText,
    detail: "This currently starts the same listening session. To read feedback from a completed session, open Recent Sessions on your dashboard.",
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
      navigate(selectedMode === "practice" ? `/practice/${latest.id}` : `/session/${latest.id}`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to start session");
    } finally {
      setLoading(false);
    }
  };

  const activeMode = MODES.find((mode) => mode.id === selectedMode)!;
  const inputClass = "w-full min-w-0 rounded-lg border border-border bg-bg px-4 py-3 text-sm text-primary placeholder:text-slate-500 outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/20";

  return (
    <div className="w-full min-w-0 p-4 sm:p-6 lg:p-8 xl:p-10">
      <div className="mb-8 border-b border-border pb-6">
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-violet-300">Your interview workspace</p>
        <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-primary">Start a Session</h1>
        <p className="text-sm text-slate-400 mt-2">
          Choose a mode, configure your session, then start practicing.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6 lg:space-y-8">
        {/* Mode Selection */}
        <fieldset disabled={loading}>
          <legend className="text-sm font-semibold text-primary mb-4">
            <span className="mr-2 text-violet-300">01</span> Choose your session mode
          </legend>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {MODES.map(({ id, name, desc, icon: Icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => setSelectedMode(id as FormData["mode"])}
                aria-pressed={selectedMode === id}
                className={clsx(
                  "relative min-w-0 text-left p-5 xl:p-6 rounded-xl border transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
                  selectedMode === id
                    ? "border-accent bg-accent/10 shadow-glow-sm"
                    : "border-border bg-surface hover:border-accent/50 hover:bg-surface-2"
                )}
              >
                <div className="mb-5 flex items-center justify-between">
                  <span className={clsx("flex h-10 w-10 items-center justify-center rounded-lg", selectedMode === id ? "bg-accent/20 text-violet-300" : "bg-surface-2 text-slate-400")}><Icon size={20} /></span>
                  <span className={clsx("flex h-5 w-5 items-center justify-center rounded-full border", selectedMode === id ? "border-accent bg-accent text-white" : "border-slate-600")}>{selectedMode === id && <Check size={13} />}</span>
                </div>
                <p className="text-sm font-medium text-primary mt-2">{name}</p>
                <p className="text-sm leading-relaxed text-slate-400 mt-2">{desc}</p>
              </button>
            ))}
          </div>
        </fieldset>

        <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,1.65fr)_minmax(280px,1fr)]">
        {/* Session Details */}
        <div className="min-w-0 bg-surface border border-border rounded-xl p-5 sm:p-6 space-y-5">
          <div><h2 className="text-sm font-semibold text-primary"><span className="mr-2 text-violet-300">02</span> Session details</h2><p className="mt-2 text-sm text-slate-400">Add a name and target so this session is easy to find later.</p></div>

          <div>
            <label htmlFor="session-title" className="text-sm text-slate-300 block mb-2">Session Title (optional)</label>
            <input
              id="session-title"
              {...register("title")}
              placeholder="e.g., Meta Onsite Prep"
              className={inputClass}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="target-role" className="text-sm text-slate-300 block mb-2 flex items-center gap-1">
                <Briefcase size={12} /> Target Role
              </label>
              <input
                id="target-role"
                {...register("target_role")}
                placeholder="Senior Engineer"
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="target-company" className="text-sm text-slate-300 block mb-2 flex items-center gap-1">
                <Building2 size={12} /> Company
              </label>
              <input
                id="target-company"
                {...register("target_company")}
                placeholder="Stripe, Google..."
                className={inputClass}
              />
            </div>
          </div>
        </div>

        <aside className="rounded-xl border border-border bg-surface p-5 sm:p-6" aria-live="polite">
          <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-primary"><Headphones size={18} className="text-violet-300" /> What to expect</div>
          <h3 className="text-base font-medium text-primary">{activeMode.name}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-400">{activeMode.detail}</p>
          <div className="mt-5 border-t border-border pt-4 text-sm leading-6 text-slate-400">{selectedMode === "practice" ? "Type or record your answers. Review the transcript before submitting." : "Start your session, choose your audio source, then enable listening when ready."}</div>
          {selectedMode === "review" && <button type="button" onClick={() => navigate("/dashboard")} className="mt-4 flex items-center gap-2 border-0 bg-transparent text-sm text-violet-300 hover:text-white">View recent sessions <ArrowRight size={15} /></button>}
        </aside>
        </div>

        <div className="flex flex-col gap-4 border-t border-border pt-6 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-400">{selectedMode === "practice" ? "Ready when you are. Your first question starts inside the session." : "Ready when you are. Listening starts inside the session."}</p>
        {/* Start Button */}
        <button
          type="submit"
          disabled={loading}
          className="w-full sm:w-auto sm:min-w-[220px] flex items-center justify-center gap-2 border-0 bg-accent hover:bg-accent-hover text-white text-sm font-semibold px-6 py-3.5 rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300 focus-visible:ring-offset-2 focus-visible:ring-offset-bg disabled:opacity-50 disabled:cursor-wait"
        >
          {loading ? (
            <><Loader2 size={18} className="animate-spin" /> Starting session...</>
          ) : (
            <>
              <Mic size={18} />
              Start Session
              <ChevronRight size={16} />
            </>
          )}
        </button>
        </div>
      </form>
    </div>
  );
}
