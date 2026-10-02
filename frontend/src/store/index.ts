import { create } from "zustand";
import { persist } from "zustand/middleware";
import { apiClient } from "../api/client";

// ── Types ─────────────────────────────────────────────────────
export interface User {
  id: string;
  email: string;
  full_name: string | null;
  plan_tier: "free" | "pro" | "enterprise";
  is_verified: boolean;
  created_at: string;
}

export interface Session {
  id: string;
  user_id: string;
  mode: "practice" | "interview" | "review";
  title: string | null;
  target_role: string | null;
  target_company: string | null;
  status: "active" | "completed" | "abandoned";
  started_at: string;
  ended_at: string | null;
  duration_secs: number | null;
  total_questions: number;
}

export interface Transcript {
  id: string;
  session_id: string;
  speaker: "user" | "interviewer";
  content: string;
  confidence: number | null;
  is_question: boolean;
  created_at: string;
}

export interface AISuggestion {
  id?: string;
  text: string;
  provider: string;
  isStreaming: boolean;
  timestamp: string;
}

// ── Auth Slice ────────────────────────────────────────────────
interface AuthSlice {
  user: User | null;
  accessToken: string | null;
  setUser: (user: User, token: string) => void;
  setAccessToken: (token: string) => void;
  logout: () => void;
  isAuthenticated: () => boolean;
}

// ── Session Slice ─────────────────────────────────────────────
interface SessionSlice {
  session: Session | null;
  sessionStatus: "idle" | "connecting" | "active" | "paused" | "ended";
  transcripts: Transcript[];
  aiSuggestions: AISuggestion[];
  currentSuggestion: string;
  currentProvider: string;
  wsRef: WebSocket | null;
  startSession: (config: CreateSessionPayload) => Promise<void>;
  endSession: () => Promise<void>;
  addTranscript: (t: Omit<Transcript, "id">) => void;
  appendSuggestionToken: (token: string, provider: string) => void;
  finalizeSuggestion: () => void;
  clearSession: () => void;
}

// ── Audio Slice ───────────────────────────────────────────────
interface AudioSlice {
  isCapturing: boolean;
  audioLevel: number;
  selectedMicId: string | null;
  captureSystemAudio: boolean;
  micEnabled: boolean;
  setCapturing: (v: boolean) => void;
  setAudioLevel: (v: number) => void;
  setMicId: (id: string) => void;
  setCaptureSystemAudio: (v: boolean) => void;
  setMicEnabled: (v: boolean) => void;
}

// ── UI Slice ──────────────────────────────────────────────────
interface UISlice {
  overlayVisible: boolean;
  sidebarOpen: boolean;
  toggleOverlay: () => void;
  toggleSidebar: () => void;
}

export interface CreateSessionPayload {
  mode: "practice" | "interview" | "review";
  title?: string;
  target_role?: string;
  target_company?: string;
  resume_id?: string;
}

// ── Combined Store ─────────────────────────────────────────────
type AppStore = AuthSlice & SessionSlice & AudioSlice & UISlice;

export const useStore = create<AppStore>()(
  persist(
    (set, get) => ({
      // ── Auth ───────────────────────────────────────────────
      user: null,
      accessToken: null,
      setUser: (user, accessToken) => {
        set({ user, accessToken });
        apiClient.defaults.headers.common["Authorization"] = `Bearer ${accessToken}`;
      },
      setAccessToken: (accessToken) => {
        set({ accessToken });
        apiClient.defaults.headers.common["Authorization"] = `Bearer ${accessToken}`;
      },
      logout: () => {
        set({ user: null, accessToken: null, session: null });
        delete apiClient.defaults.headers.common["Authorization"];
      },
      isAuthenticated: () => !!get().user && !!get().accessToken,

      // ── Session ────────────────────────────────────────────
      session: null,
      sessionStatus: "idle",
      transcripts: [],
      aiSuggestions: [],
      currentSuggestion: "",
      currentProvider: "",
      wsRef: null,

      startSession: async (config) => {
        set({ sessionStatus: "connecting" });
        const { data } = await apiClient.post<Session>("/sessions/", config);
        set({ session: data, sessionStatus: "active", transcripts: [], aiSuggestions: [], currentSuggestion: "", currentProvider: "" });
      },

      endSession: async () => {
        const { session } = get();
        if (!session) return;
        await apiClient.post(`/sessions/${session.id}/end`);
        set({ sessionStatus: "ended" });
      },

      addTranscript: (t) =>
        set((s) => ({
          transcripts: [...s.transcripts, { id: crypto.randomUUID(), ...t }],
        })),

      appendSuggestionToken: (token, provider) =>
        set((s) => ({ currentSuggestion: s.currentSuggestion + token, currentProvider: provider })),

      finalizeSuggestion: () =>
        set((s) => ({
          aiSuggestions: [
            ...s.aiSuggestions,
            {
              text: s.currentSuggestion,
              provider: s.currentProvider,
              isStreaming: false,
              timestamp: new Date().toISOString(),
            },
          ],
          currentSuggestion: "",
        })),

      clearSession: () =>
        set({
          session: null,
          sessionStatus: "idle",
          transcripts: [],
          aiSuggestions: [],
          currentSuggestion: "",
        }),

      // ── Audio ──────────────────────────────────────────────
      isCapturing: false,
      audioLevel: 0,
      selectedMicId: null,
      captureSystemAudio: true,
      micEnabled: false,
      setCapturing: (v) => set({ isCapturing: v }),
      setAudioLevel: (v) => set({ audioLevel: v }),
      setMicId: (id) => set({ selectedMicId: id }),
      setCaptureSystemAudio: (v) => set({ captureSystemAudio: v }),
      setMicEnabled: (v) => set({ micEnabled: v }),

      // ── UI ─────────────────────────────────────────────────
      overlayVisible: false,
      sidebarOpen: true,
      toggleOverlay: () => set((s) => ({ overlayVisible: !s.overlayVisible })),
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
    }),
    {
      name: "interviewcopilot-store",
      partialize: (s) => ({
        user: s.user,
        accessToken: s.accessToken,
        captureSystemAudio: s.captureSystemAudio,
        micEnabled: s.micEnabled,
      }),
    }
  )
);
