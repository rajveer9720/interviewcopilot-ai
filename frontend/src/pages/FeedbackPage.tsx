import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { apiClient } from "../api/client";
import { RadialBarChart, RadialBar, ResponsiveContainer, Tooltip } from "recharts";
import { ArrowLeft, TrendingUp, MessageSquare, Code, Star, Zap } from "lucide-react";

interface Feedback {
  scores: { overall: number; communication: number; technical: number; star_method: number; confidence: number };
  strengths: string[];
  improvements: string[];
  detailed_report: string;
  created_at: string;
}

const ScoreGauge = ({ label, score, color, icon: Icon }: any) => (
  <div className="bg-surface-2 rounded-lg p-3 text-center">
    <Icon size={16} className={`${color} mx-auto mb-1`} />
    <p className="text-xs text-muted mb-1">{label}</p>
    <p className={`text-lg font-semibold ${color}`}>{score?.toFixed(1) ?? "—"}</p>
    <div className="mt-2 h-1 bg-border rounded-full overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{ width: `${(score / 10) * 100}%`, backgroundColor: "currentColor" }}
      />
    </div>
  </div>
);

export default function FeedbackPage() {
  const { id } = useParams<{ id: string }>();
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await apiClient.get(`/feedback/sessions/${id}/feedback`);
        if (data.status === "pending") {
          setPending(true);
          setTimeout(load, 3000);  // poll every 3s
        } else {
          setFeedback(data);
        }
      } catch {
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent" />
      </div>
    );
  }

  if (pending) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-4 text-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-accent mb-2" />
        <p className="text-primary font-medium">Generating your feedback report...</p>
        <p className="text-sm text-muted">This usually takes 15–30 seconds</p>
      </div>
    );
  }

  if (!feedback) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-4">
        <p className="text-muted">No feedback available for this session.</p>
        <Link to="/dashboard" className="text-accent text-sm hover:underline">← Back to Dashboard</Link>
      </div>
    );
  }

  const overallColor =
    feedback.scores.overall >= 8 ? "text-success"
    : feedback.scores.overall >= 6 ? "text-warning"
    : "text-error";

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <Link to="/dashboard" className="flex items-center gap-1 text-sm text-muted hover:text-primary mb-6">
        <ArrowLeft size={14} /> Dashboard
      </Link>

      {/* Overall Score Hero */}
      <div className="bg-surface border border-border rounded-lg p-6 mb-6 text-center">
        <p className="text-xs text-muted uppercase tracking-wider mb-2">Overall Score</p>
        <p className={`text-6xl font-bold ${overallColor}`}>{feedback.scores.overall?.toFixed(1)}</p>
        <p className="text-muted text-sm mt-1">/ 10.0</p>
      </div>

      {/* Sub-Scores */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <ScoreGauge label="Communication" score={feedback.scores.communication} color="text-accent" icon={MessageSquare} />
        <ScoreGauge label="Technical"     score={feedback.scores.technical}     color="text-success"  icon={Code} />
        <ScoreGauge label="STAR Method"   score={feedback.scores.star_method}   color="text-warning"  icon={Star} />
        <ScoreGauge label="Confidence"    score={feedback.scores.confidence}    color="text-primary"  icon={Zap} />
      </div>

      {/* Strengths & Improvements */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-surface border border-success/20 rounded-lg p-4">
          <p className="text-xs text-success uppercase tracking-wider mb-3 font-medium">Strengths</p>
          <ul className="space-y-2">
            {feedback.strengths?.map((s, i) => (
              <li key={i} className="text-sm text-primary flex items-start gap-2">
                <span className="text-success mt-0.5">✓</span>
                {s}
              </li>
            ))}
          </ul>
        </div>
        <div className="bg-surface border border-warning/20 rounded-lg p-4">
          <p className="text-xs text-warning uppercase tracking-wider mb-3 font-medium">Improve</p>
          <ul className="space-y-2">
            {feedback.improvements?.map((s, i) => (
              <li key={i} className="text-sm text-primary flex items-start gap-2">
                <span className="text-warning mt-0.5">→</span>
                {s}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Detailed Report */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <p className="text-xs text-muted uppercase tracking-wider mb-3">Detailed Report</p>
        <p className="text-sm text-primary leading-relaxed whitespace-pre-wrap">
          {feedback.detailed_report}
        </p>
      </div>

      {/* Actions */}
      <div className="flex gap-3 mt-6">
        <Link
          to="/practice"
          className="flex-1 py-2.5 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-lg text-center transition-colors"
        >
          Practice Again
        </Link>
        <Link
          to="/dashboard"
          className="flex-1 py-2.5 bg-surface border border-border hover:bg-surface-2 text-primary text-sm font-medium rounded-lg text-center transition-colors"
        >
          View Dashboard
        </Link>
      </div>
    </div>
  );
}
