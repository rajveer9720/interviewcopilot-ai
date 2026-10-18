import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useStore } from "../store";
import { apiClient } from "../api/client";
import { Mic, TrendingUp, Clock, Target, ChevronRight } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";

interface DashboardData {
  total_sessions:      number;
  sessions_this_month: number;
  average_score:       number;
  total_practice_mins: number;
  plan_tier:           string;
  recent_sessions:     any[];
}

export default function DashboardPage() {
  const { user } = useStore();
  const [data, setData] = useState<DashboardData | null>(null);
  const [scores, setScores] = useState<any[]>([]);

  useEffect(() => {
    apiClient.get("/analytics/dashboard").then((r) => setData(r.data));
    apiClient.get("/analytics/scores?range=30").then((r) => setScores(r.data));
  }, []);

  const StatCard = ({
    icon: Icon, label, value, sub, color = "text-accent",
  }: any) => (
    <div className="bg-surface border border-border rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <Icon size={16} className={color} />
        <span className="text-xs text-muted uppercase tracking-wider">{label}</span>
      </div>
      <p className="text-2xl font-semibold text-primary">{value}</p>
      {sub && <p className="text-xs text-muted mt-1">{sub}</p>}
    </div>
  );

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-primary">
          Welcome back, {user?.full_name?.split(" ")[0] || "engineer"} 👋
        </h1>
        <p className="text-sm text-muted mt-1">
          Track your interview prep progress and improve consistently.
        </p>
      </div>

      {/* Start Session CTA */}
      <Link
        to="/practice"
        className="flex items-center justify-between p-4 mb-6 bg-accent/10 border border-accent/30 rounded-lg hover:bg-accent/15 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
            <Mic size={16} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-medium text-primary">Start Practice Session</p>
            <p className="text-xs text-muted">Practice with AI coaching in real-time</p>
          </div>
        </div>
        <ChevronRight size={16} className="text-accent" />
      </Link>

      {/* Stats Grid */}
      {data && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard
            icon={Target}
            label="Total Sessions"
            value={data.total_sessions}
            sub="all time"
          />
          <StatCard
            icon={TrendingUp}
            label="Avg Score"
            value={data.average_score > 0 ? `${data.average_score}/10` : "—"}
            sub="last 30 days"
            color="text-success"
          />
          <StatCard
            icon={Clock}
            label="Practice Time"
            value={`${data.total_practice_mins}m`}
            sub="total"
            color="text-warning"
          />
          <StatCard
            icon={Mic}
            label="This Month"
            value={data.sessions_this_month}
            sub="sessions"
          />
        </div>
      )}

      {/* Score Chart */}
      {scores.length > 0 && (
        <div className="bg-surface border border-border rounded-lg p-4 mb-6">
          <h2 className="text-sm font-medium text-primary mb-4">Score Trend</h2>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={scores}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2D2D3D" />
              <XAxis
                dataKey="date"
                tickFormatter={(v) => new Date(v).toLocaleDateString("en", { month: "short", day: "numeric" })}
                tick={{ fill: "#7777AA", fontSize: 11 }}
                axisLine={{ stroke: "#2D2D3D" }}
              />
              <YAxis domain={[0, 10]} tick={{ fill: "#7777AA", fontSize: 11 }} axisLine={{ stroke: "#2D2D3D" }} />
              <Tooltip
                contentStyle={{ background: "#1E1E2E", border: "1px solid #2D2D3D", borderRadius: 8 }}
                labelStyle={{ color: "#7777AA" }}
              />
              <Line type="monotone" dataKey="overall" stroke="#6C63FF" strokeWidth={2} dot={false} name="Overall" />
              <Line type="monotone" dataKey="technical" stroke="#22C55E" strokeWidth={1.5} dot={false} name="Technical" />
              <Line type="monotone" dataKey="communication" stroke="#F59E0B" strokeWidth={1.5} dot={false} name="Communication" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Recent Sessions */}
      {data && data.recent_sessions.length > 0 && (
        <div className="bg-surface border border-border rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <h2 className="text-sm font-medium text-primary">Recent Sessions</h2>
          </div>
          <div className="divide-y divide-border">
            {data.recent_sessions.map((s) => (
              <Link
                key={s.id}
                to={s.mode === "practice" ? `/practice/${s.id}` : `/feedback/${s.id}`}
                className="flex items-center justify-between px-4 py-3 hover:bg-surface-2 transition-colors"
              >
                <div>
                  <p className="text-sm text-primary">{s.title || s.mode}</p>
                  <p className="text-xs text-muted">
                    {new Date(s.started_at).toLocaleDateString()} ·{" "}
                    {s.duration_secs ? `${Math.round(s.duration_secs / 60)}m` : "in progress"}
                  </p>
                </div>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${
                    s.status === "completed" ? "bg-success/10 text-success" : "bg-warning/10 text-warning"
                  }`}
                >
                  {s.status}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
