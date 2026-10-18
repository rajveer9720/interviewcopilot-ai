import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowRight, CheckCircle2, Loader2, MessageSquare, Send } from "lucide-react";
import { apiClient } from "../api/client";
import { useStore } from "../store";
import VoiceAnswerInput from "../components/VoiceAnswerInput";

interface Turn { id: string; question: string; answer: string | null; feedback: string | null }
interface Review { scores: { overall: number; communication: number; technical: number }; strengths: string[]; improvements: string[]; report: string }
interface PracticeState { status: string; max_questions: number; turns: Turn[]; review?: Review | null }

export default function MockInterviewPage() {
  const { id } = useParams();
  const [state, setState] = useState<PracticeState | null>(null);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [voiceNotice, setVoiceNotice] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const inFlight = useRef(false);
  const latest = state?.turns[state.turns.length - 1];
  const completed = state?.status === "completed";

  async function load() {
    setLoading(true); setError("");
    try { setState((await apiClient.get(`/sessions/${id}/practice`)).data); }
    catch (err: any) { setError(err.response?.data?.detail || "Could not load practice. Please retry."); }
    finally { setLoading(false); }
  }
  useEffect(() => { setState(null); setAnswer(""); void load(); }, [id]);

  async function generateReview() {
    setReviewBusy(true); setError("");
    try {
      const { data } = await apiClient.post(`/sessions/${id}/practice/review`, {}, { timeout: 90000 });
      setState((value) => value ? { ...value, review: data } : value);
    } catch (err: any) { setError(err.response?.data?.detail || "Review could not load. Your answers are saved; retry the review."); }
    finally { setReviewBusy(false); }
  }

  function appendTranscript(text: string): boolean {
    const combined = answer.trim() ? `${answer.trim()}\n\n${text}` : text;
    if (combined.length > 8000) {
      setVoiceNotice("Transcript exceeds the answer limit. Shorten your answer, then retry transcription.");
      return false;
    }
    setAnswer(combined); setVoiceNotice("Transcript added. Review it before submitting.");
    return true;
  }

  async function act(action: "start" | "answer" | "next" | "end") {
    if (inFlight.current || voiceBusy || reviewBusy) return;
    inFlight.current = true; setBusy(true); setError("");
    try {
      if (action === "end") {
        await apiClient.post(`/sessions/${id}/end`);
        setState((value) => value ? { ...value, status: "completed" } : value);
        useStore.getState().clearSession();
        if (state?.turns.some((turn) => turn.answer !== null)) await generateReview();
      } else {
        const { data } = await apiClient.post(`/sessions/${id}/practice`, {
          action, question_id: latest?.id, answer: action === "answer" ? answer : "",
        });
        setState(data); setAnswer(""); setVoiceNotice("");
      }
    } catch (err: any) { setError(err.response?.data?.detail || "Request failed. Please retry; your answer is still here."); }
    finally { inFlight.current = false; setBusy(false); }
  }

  const button = "inline-flex w-full sm:w-auto items-center justify-center gap-2 rounded-lg border-0 bg-accent px-5 py-3 text-sm font-semibold text-white hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed";
  return <div className="w-full min-w-0 p-4 sm:p-6 lg:p-8 xl:p-10">
    <header className="mb-6 flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-center sm:justify-between">
      <div><p className="mb-2 text-xs uppercase tracking-widest text-violet-300">AI mock interview</p><h1 className="text-2xl font-semibold sm:text-3xl">Practice with an interviewer</h1><p className="mt-2 text-sm text-slate-400">Answer in your own words. Get feedback before moving on.</p></div>
      {state && !completed && <button disabled={busy || voiceBusy || reviewBusy} onClick={() => act("end")} className="shrink-0 rounded-lg border border-border px-4 py-2 text-sm disabled:opacity-50">End practice</button>}
    </header>
    {error && <div role="alert" className="mb-5 rounded-lg border border-error/30 bg-error/10 p-4 text-sm text-red-300">{error}{!state && <button onClick={load} className="ml-3 underline">Retry</button>}</div>}
    {loading ? <div role="status" className="flex items-center gap-2 text-slate-400"><Loader2 className="animate-spin" size={18} /> Loading practice...</div> : state && <>
      {completed && <div className="mb-6 rounded-xl border border-success/30 bg-success/10 p-5"><h2 className="flex items-center gap-2 font-semibold"><CheckCircle2 size={20} /> Practice saved</h2><p className="mt-2 text-sm text-slate-300">Your questions, answers and feedback are saved. Review your performance below.</p><Link to="/practice" className="mt-3 inline-block text-sm text-violet-300">Start another practice</Link></div>}
      {completed && <section className="mb-6 rounded-xl border border-border bg-surface p-5 sm:p-6">
        <h2 className="text-lg font-semibold">Overall practice review</h2>
        {reviewBusy ? <p role="status" className="mt-4 flex items-center gap-2 text-sm text-violet-300"><Loader2 size={17} className="animate-spin" /> Reviewing your submitted answers...</p> : state.review ? <>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">{Object.entries(state.review.scores).map(([label, score]) => <div key={label} className="rounded-lg border border-border bg-bg p-4"><p className="text-xs capitalize text-slate-400">{label === "communication" ? "Answer clarity" : label}</p><p className="mt-2 text-2xl font-semibold text-violet-300">{score.toFixed(1)}<span className="text-sm text-slate-400"> / 10</span></p></div>)}</div>
          <div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-2"><div><h3 className="text-sm font-semibold text-green-300">Strengths</h3><ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-6 text-slate-300">{state.review.strengths.map((item, i) => <li key={i}>{item}</li>)}</ul></div><div><h3 className="text-sm font-semibold text-amber-300">Focus next</h3><ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-6 text-slate-300">{state.review.improvements.map((item, i) => <li key={i}>{item}</li>)}</ul></div></div>
          <p className="mt-5 whitespace-pre-wrap break-words border-t border-border pt-5 text-sm leading-7 text-slate-300">{state.review.report}</p><p className="mt-3 text-xs text-slate-400">Scores assess answer content and transcript clarity, not vocal delivery or confidence.</p>
        </> : state.turns.some((turn) => turn.answer !== null) ? <button onClick={generateReview} className={`${button} mt-4`}>Generate overall review</button> : <p className="mt-3 text-sm text-slate-400">No answers were submitted. Complete at least one answer in a new practice to receive scores.</p>}
      </section>}
      <div className="grid min-w-0 grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(250px,1fr)]">
        <section className="min-w-0 rounded-xl border border-border bg-surface p-5 sm:p-6">
          {!latest ? <><MessageSquare className="mb-4 text-violet-300" /><h2 className="text-lg font-semibold">Ready for your first question?</h2><p className="my-4 text-sm leading-6 text-slate-400">The interviewer asks one question at a time. Type your answer to receive specific feedback. You can type or record your answer, then edit the transcript before submitting.</p>{!completed && <button className={button} disabled={busy || voiceBusy || reviewBusy} onClick={() => act("start")}>Start interview <ArrowRight size={17} /></button>}</> : <>
            <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-violet-300">Question {state.turns.length} of {state.max_questions}</p>
            <h2 className="whitespace-pre-wrap break-words text-lg font-medium leading-8 sm:text-xl">{latest.question}</h2>
            {latest.answer !== null ? <><h3 className="mb-2 mt-6 text-sm font-semibold">Your answer</h3><p className="whitespace-pre-wrap break-words text-sm leading-7 text-slate-300">{latest.answer}</p><div className="mt-6 rounded-lg border border-accent/25 bg-accent/5 p-4"><h3 className="mb-2 text-sm font-semibold text-violet-300">Interviewer feedback</h3><p className="whitespace-pre-wrap break-words text-sm leading-7 text-slate-300">{latest.feedback}</p></div>{!completed && <button className={`${button} mt-6`} disabled={busy || voiceBusy || reviewBusy} onClick={() => act(state.turns.length >= state.max_questions ? "end" : "next")}>{state.turns.length >= state.max_questions ? "Finish practice" : "Next question"}<ArrowRight size={17} /></button>}</> : !completed && <form className="mt-6" onSubmit={(e) => { e.preventDefault(); void act("answer"); }}><VoiceAnswerInput key={latest.id} sessionId={id!} questionId={latest.id} disabled={busy || reviewBusy} onTranscript={appendTranscript} onBusyChange={setVoiceBusy} />{voiceNotice && <p role="status" className="mb-3 text-sm text-violet-300">{voiceNotice}</p>}<label htmlFor="candidate-answer" className="mb-2 block text-sm font-medium">Your answer</label><textarea id="candidate-answer" value={answer} onChange={(e) => setAnswer(e.target.value)} disabled={busy || voiceBusy || reviewBusy} maxLength={8000} rows={9} placeholder="Explain your approach, reasoning and examples..." className="w-full resize-y rounded-lg border border-border bg-bg p-4 text-sm leading-7 outline-none focus:border-accent focus:ring-2 focus:ring-accent/20" /><div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><span className="text-xs text-slate-400">{answer.length}/8000 characters</span><button className={button} disabled={busy || voiceBusy || reviewBusy || !answer.trim()}><Send size={16} /> Submit answer</button></div></form>}
          </>}
          {busy && <p role="status" className="mt-4 flex items-center gap-2 text-sm text-violet-300"><Loader2 size={16} className="animate-spin" /> Working on your interview...</p>}
        </section>
        <aside className="min-w-0 rounded-xl border border-border bg-surface p-5"><h2 className="text-sm font-semibold">Practice guide</h2><ol className="mt-4 space-y-3 text-sm leading-6 text-slate-400"><li>1. Read the question and organize your thoughts.</li><li>2. Answer with reasoning and a concrete example.</li><li>3. Use the feedback to improve your next answer.</li></ol><p className="mt-5 border-t border-border pt-4 text-xs leading-5 text-slate-400">Submitted answers are saved. Unsubmitted drafts are lost when you leave or refresh. AI feedback can be imperfect; verify technical claims.</p></aside>
      </div>
      {state.turns.length > 1 && <section className="mt-8"><h2 className="mb-4 text-lg font-semibold">Earlier questions</h2><div className="space-y-3">{state.turns.slice(0, -1).map((turn, index) => <details key={turn.id} className="rounded-xl border border-border bg-surface p-4"><summary className="cursor-pointer break-words text-sm font-medium">{index + 1}. {turn.question}</summary><p className="mt-4 whitespace-pre-wrap break-words text-sm leading-7 text-slate-300">{turn.answer}</p><h3 className="mt-4 text-sm font-semibold text-violet-300">Feedback</h3><p className="mt-2 whitespace-pre-wrap break-words text-sm leading-7 text-slate-400">{turn.feedback}</p></details>)}</div></section>}
    </>}
  </div>;
}
