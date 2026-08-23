import { useEffect, useRef, useState } from "react";
import { useStore } from "../store";
import { apiClient } from "../api/client";
import { User, Mic, Cpu, Shield, FileText, Upload, Trash2, Loader2 } from "lucide-react";
import toast from "react-hot-toast";

interface ResumeEntry {
  id: string;
  filename: string;
  skills: string[];
  created_at: string;
}

function getErrorMessage(err: any, fallback: string): string {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join(", ");
  return fallback;
}

export default function SettingsPage() {
  const { user, captureSystemAudio, setCaptureSystemAudio, micEnabled, setMicEnabled } = useStore();

  const [resumes, setResumes] = useState<ResumeEntry[]>([]);
  const [resumesLoading, setResumesLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    apiClient
      .get<ResumeEntry[]>("/resumes/")
      .then(({ data }) => setResumes(data))
      .catch(() => toast.error("Failed to load resumes"))
      .finally(() => setResumesLoading(false));
  }, []);

  const handleUploadClick = () => fileInputRef.current?.click();

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const { data } = await apiClient.post<ResumeEntry>("/resumes/", formData, {
        headers: { "Content-Type": undefined },
      });
      setResumes((prev) => [data, ...prev]);
      toast.success("Resume uploaded");
    } catch (err: any) {
      toast.error(getErrorMessage(err, "Upload failed"));
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    const prev = resumes;
    setResumes((r) => r.filter((res) => res.id !== id));
    try {
      await apiClient.delete(`/resumes/${id}`);
    } catch {
      setResumes(prev);
      toast.error("Failed to delete resume");
    }
  };

  const Section = ({ icon: Icon, title, children }: any) => (
    <div className="bg-surface border border-border rounded-lg overflow-hidden mb-4">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
        <Icon size={15} className="text-muted" />
        <p className="text-sm font-medium text-primary">{title}</p>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );

  const SettingRow = ({ label, description, children }: any) => (
    <div className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0 border-b border-border last:border-0">
      <div>
        <p className="text-sm text-primary">{label}</p>
        {description && <p className="text-xs text-muted mt-0.5">{description}</p>}
      </div>
      {children}
    </div>
  );

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-primary">Settings</h1>
      </div>

      <Section icon={User} title="Profile">
        <SettingRow label="Name" description={user?.email}>
          <input
            defaultValue={user?.full_name || ""}
            className="bg-surface-2 border border-border rounded px-3 py-1.5 text-sm text-primary focus:outline-none focus:border-accent w-48"
          />
        </SettingRow>
        <SettingRow label="Email">
          <span className="text-sm text-muted">{user?.email}</span>
        </SettingRow>
        <SettingRow label="Plan">
          <span className="text-xs bg-accent/10 text-accent px-2 py-0.5 rounded-full capitalize font-medium">
            {user?.plan_tier}
          </span>
        </SettingRow>
      </Section>

      <Section icon={FileText} title="Resume">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.doc,.docx"
          className="hidden"
          onChange={handleFileSelected}
        />

        {resumesLoading ? (
          <p className="text-sm text-muted">Loading...</p>
        ) : (
          <>
            {resumes.length === 0 && (
              <p className="text-sm text-muted mb-3">
                No resume uploaded yet. Upload one so AI coaching can use your background.
              </p>
            )}
            {resumes.map((r) => (
              <div
                key={r.id}
                className="flex items-center justify-between gap-4 py-3 first:pt-0 border-b border-border last:border-0"
              >
                <div className="min-w-0">
                  <p className="text-sm text-primary truncate">{r.filename}</p>
                  {r.skills?.length > 0 && (
                    <p className="text-xs text-muted mt-0.5 truncate">
                      {r.skills.slice(0, 6).join(", ")}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => handleDelete(r.id)}
                  className="text-muted hover:text-error transition-colors shrink-0"
                  aria-label="Delete resume"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </>
        )}

        <button
          onClick={handleUploadClick}
          disabled={uploading}
          className="w-full mt-3 flex items-center justify-center gap-2 text-sm text-accent border border-accent/30 rounded-lg py-2 hover:bg-accent/10 transition-colors disabled:opacity-50"
        >
          {uploading ? (
            <Loader2 size={15} className="animate-spin" />
          ) : (
            <Upload size={15} />
          )}
          {uploading ? "Uploading..." : "Upload Resume (PDF or Word, max 5MB)"}
        </button>
      </Section>

      <Section icon={Mic} title="Audio">
        <SettingRow label="Microphone" description="Select your input device">
          <select className="bg-surface-2 border border-border rounded px-3 py-1.5 text-sm text-primary focus:outline-none focus:border-accent">
            <option>Default Microphone</option>
          </select>
        </SettingRow>
        <SettingRow
          label="Capture System Audio"
          description="Captures Zoom, Teams, and Meet audio (Windows only)"
        >
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              className="sr-only peer"
              checked={captureSystemAudio}
              onChange={(e) => setCaptureSystemAudio(e.target.checked)}
            />
            <div className="w-9 h-5 bg-border peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-accent" />
          </label>
        </SettingRow>
        <SettingRow
          label="Listen to My Microphone"
          description="Turn off for practice mode — only system audio (the interviewer's voice) is transcribed, your own voice is ignored"
        >
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              className="sr-only peer"
              checked={micEnabled}
              onChange={(e) => setMicEnabled(e.target.checked)}
            />
            <div className="w-9 h-5 bg-border peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-accent" />
          </label>
        </SettingRow>
      </Section>

      <Section icon={Cpu} title="AI Provider">
        <SettingRow label="Preferred LLM" description="Pro plan required for GPT-4o">
          <select className="bg-surface-2 border border-border rounded px-3 py-1.5 text-sm text-primary focus:outline-none focus:border-accent">
            <option value="auto">Auto (recommended)</option>
            <option value="openai">GPT-4o (Pro)</option>
            <option value="gemini">Gemini Pro</option>
          </select>
        </SettingRow>
        <SettingRow label="Response Style">
          <select className="bg-surface-2 border border-border rounded px-3 py-1.5 text-sm text-primary focus:outline-none focus:border-accent">
            <option>Coaching (detailed)</option>
            <option>Concise (bullets)</option>
          </select>
        </SettingRow>
      </Section>

      <Section icon={Shield} title="Privacy">
        <SettingRow label="Data Retention" description="Transcripts are retained for 90 days by default">
          <select className="bg-surface-2 border border-border rounded px-3 py-1.5 text-sm text-primary focus:outline-none focus:border-accent">
            <option>90 days</option>
            <option>30 days</option>
            <option>7 days</option>
          </select>
        </SettingRow>
        <SettingRow label="Delete All My Data" description="This is irreversible">
          <button className="text-xs text-error border border-error/30 px-3 py-1.5 rounded hover:bg-error/10 transition-colors">
            Delete Data
          </button>
        </SettingRow>
      </Section>

      <button className="w-full py-2.5 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-lg transition-colors">
        Save Settings
      </button>
    </div>
  );
}
