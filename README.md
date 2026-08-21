# InterviewCopilot AI

> AI-powered Interview Practice & Live Meeting Assistant for Software Engineers

**Ethical AI coaching tool — Built for learning, practice, and skill improvement.**

InterviewCopilot AI listens during mock practice sessions, captures real-time speech, generates intelligent answer coaching, and provides post-session analytics to help software engineers consistently improve their interviewing skills.

---

## Table of Contents

1. [Product Architecture](#1-product-architecture)
2. [Audio Processing Layer](#2-audio-processing-layer)
3. [Backend Structure](#3-backend-structure)
4. [Database Schema](#4-database-schema)
5. [API Design](#5-api-design)
6. [Frontend Architecture](#6-frontend-architecture)
7. [Electron Desktop Strategy](#7-electron-desktop-strategy)
8. [Multi-LLM Integration](#8-multi-llm-integration)
9. [Scalability Plan](#9-scalability-plan)
10. [Security & Privacy](#10-security--privacy)
11. [DevOps & Deployment](#11-devops--deployment)
12. [Monetization Strategy](#12-monetization-strategy)
13. [21-Day Development Roadmap](#13-21-day-development-roadmap)
14. [Resume-Ready Product Description](#14-resume-ready-product-description)

---

## 1. Product Architecture

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ELECTRON DESKTOP APP                         │
│                                                                     │
│   ┌──────────────┐   ┌──────────────┐   ┌───────────────────────┐  │
│   │  React UI    │   │ Audio Engine │   │  IPC Bridge (Main)    │  │
│   │  (Overlay)   │◄──│  (WASAPI)    │──►│  Node.js Electron     │  │
│   └──────┬───────┘   └──────────────┘   └─────────┬─────────────┘  │
│          │                                         │                │
└──────────┼─────────────────────────────────────────┼────────────────┘
           │  HTTPS / WebSocket                      │ HTTPS
           ▼                                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND                           │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  Auth Layer  │  │  WS Router   │  │  REST API Router     │   │
│  │  (JWT)       │  │  (Streaming) │  │  (Sessions/Users)    │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
│         │                 │                      │               │
│  ┌──────▼─────────────────▼──────────────────────▼───────────┐  │
│  │                    SERVICE LAYER                           │  │
│  │  ┌────────────┐ ┌────────────┐ ┌───────────┐ ┌─────────┐ │  │
│  │  │ Transcript │ │ LLM Router │ │  Resume   │ │Feedback │ │  │
│  │  │  Service   │ │  Service   │ │  Engine   │ │ Engine  │ │  │
│  │  └────────────┘ └────────────┘ └───────────┘ └─────────┘ │  │
│  └─────────────────────────┬──────────────────────────────────┘  │
│                            │                                     │
│  ┌─────────────────────────▼──────────────────────────────────┐  │
│  │                  INFRASTRUCTURE LAYER                       │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │  │
│  │  │PostgreSQL│  │  Redis   │  │  OpenAI  │  │  Gemini  │  │  │
│  │  │          │  │  Cache   │  │ Whisper  │  │   Pro    │  │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Architecture Decision: Modular Monolith

**Decision: Modular Monolith (not microservices) for v1**

| Factor | Reasoning |
|--------|-----------|
| Team size | Solo / small team — microservices add operational overhead |
| Latency | Internal function calls are faster than network hops for real-time audio |
| Deployment | Single Docker container simplifies initial deployment |
| Scaling path | Modules are domain-isolated — easy to extract as services at scale |
| WebSockets | Stateful WS connections are simpler in a monolith |

**Module boundaries are enforced via packages, not network calls.** When user count exceeds 500 concurrent, audio transcription and LLM routing are extracted as dedicated async workers.

### Component Diagram

```
interviewcopilot-ai/
├── backend/           ← FastAPI (modular monolith)
│   ├── auth/          ← JWT auth domain
│   ├── sessions/      ← Interview session domain
│   ├── transcripts/   ← Speech-to-text domain
│   ├── ai/            ← LLM router + providers
│   ├── resume/        ← Resume parsing + context engine
│   ├── feedback/      ← Scoring + analytics domain
│   ├── billing/       ← Stripe subscription domain
│   └── core/          ← Shared infra (DB, Redis, config)
├── frontend/          ← React + TailwindCSS
├── electron/          ← Electron main process
└── infra/             ← Docker, Nginx, CI/CD
```

### Multi-LLM Abstraction Layer

```
Request
  │
  ▼
┌─────────────────────────────────┐
│        LLM Router Service        │
│  - Reads user plan tier          │
│  - Checks provider availability  │
│  - Applies cost budget logic     │
└──────────────┬──────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
  ┌─────────┐      ┌─────────┐
  │ OpenAI  │      │ Gemini  │
  │Provider │      │Provider │
  └─────────┘      └─────────┘
       │                │
       └───────┬─────────┘
               ▼
        Response Ranker
        (quality score)
               │
               ▼
        Final Response
```

---

## 2. Audio Processing Layer

### Windows System Audio Capture (WASAPI Loopback)

WASAPI (Windows Audio Session API) loopback mode captures **system audio output** (what you hear through speakers/headphones) without requiring virtual audio cables. This captures audio from Zoom, Google Meet, and Teams natively.

```
Audio Flow:
┌─────────────────┐    ┌──────────────────┐    ┌─────────────┐
│  Zoom / Meet /  │───►│  WASAPI Loopback  │───►│  PCM Buffer │
│  Teams audio    │    │  (system audio)   │    │  16kHz mono │
└─────────────────┘    └──────────────────┘    └──────┬──────┘
                                                       │
┌─────────────────┐    ┌──────────────────┐           │
│  Microphone     │───►│  WASAPI Capture   │───────────┤
│  (user voice)   │    │  (mic input)      │           │
└─────────────────┘    └──────────────────┘           │
                                                       ▼
                                               ┌──────────────┐
                                               │ Audio Merger │
                                               │ (mix streams)│
                                               └──────┬───────┘
                                                      │
                                                      ▼
                                               ┌──────────────┐
                                               │ WebSocket     │
                                               │ Chunked Send  │
                                               │ (250ms chunks)│
                                               └──────────────┘
```

### Streaming Pipeline Design

- **Chunk size:** 250ms audio segments (4KB at 16kHz/16-bit/mono)
- **Format:** PCM 16-bit, 16000 Hz, mono (Whisper optimal format)
- **Latency target:** < 800ms end-to-end (capture → transcript → AI response)
- **Buffer strategy:** Ring buffer with 2s sliding window for context overlap

### WebSocket Streaming Design

```
Client                          Server
  │                               │
  │──── WS: /ws/session/{id} ────►│
  │                               │
  │──── {type: "audio_chunk"} ───►│ → queue → Whisper STT
  │                               │
  │◄─── {type: "transcript"} ─────│ (partial)
  │◄─── {type: "transcript"} ─────│ (final)
  │                               │ → LLM Router
  │◄─── {type: "ai_suggestion"} ──│ (streaming tokens)
  │◄─── {type: "ai_suggestion"} ──│
  │◄─── {type: "ai_complete"} ────│
  │                               │
  │──── {type: "session_end"} ───►│ → Feedback Engine
  │◄─── {type: "feedback_ready"} ─│
```

---

## 3. Backend Structure

### Clean Architecture Folder Structure

```
backend/
├── main.py                    ← FastAPI app factory
├── config.py                  ← Pydantic settings
├── dependencies.py            ← DI container
│
├── core/                      ← Shared infrastructure
│   ├── database.py            ← SQLAlchemy async engine
│   ├── redis.py               ← Redis client
│   ├── security.py            ← JWT utilities
│   ├── exceptions.py          ← Custom exceptions
│   └── middleware.py          ← CORS, rate limit, logging
│
├── auth/                      ← Authentication domain
│   ├── router.py              ← /auth endpoints
│   ├── service.py             ← Business logic
│   ├── models.py              ← SQLAlchemy models
│   ├── schemas.py             ← Pydantic schemas
│   └── dependencies.py        ← get_current_user
│
├── sessions/                  ← Session domain
│   ├── router.py
│   ├── service.py
│   ├── models.py
│   ├── schemas.py
│   └── ws_handler.py          ← WebSocket session handler
│
├── transcripts/               ← Transcript domain
│   ├── service.py             ← STT + storage
│   ├── models.py
│   ├── schemas.py
│   └── whisper_client.py      ← OpenAI Whisper wrapper
│
├── ai/                        ← LLM domain
│   ├── router.py              ← LLM routing logic
│   ├── providers/
│   │   ├── base.py            ← Abstract provider interface
│   │   ├── openai_provider.py
│   │   └── gemini_provider.py
│   ├── prompt_builder.py      ← Context-aware prompt engineering
│   └── response_ranker.py     ← Score + rank responses
│
├── resume/                    ← Resume domain
│   ├── service.py
│   ├── parser.py              ← PDF/DOCX parsing
│   ├── context_engine.py      ← Match resume to question
│   └── storage.py             ← S3 upload/retrieve
│
├── feedback/                  ← Feedback domain
│   ├── service.py
│   ├── scorer.py              ← STAR method scoring
│   ├── analytics.py           ← Session analytics
│   └── models.py
│
├── billing/                   ← Billing domain
│   ├── router.py              ← Stripe webhooks
│   ├── service.py
│   ├── stripe_client.py
│   └── models.py
│
└── workers/                   ← Background tasks
    ├── audio_worker.py        ← Async audio processing
    └── feedback_worker.py     ← Post-session processing
```

### Domain-Driven Design Approach

Each domain owns:
- Its **models** (database entities)
- Its **schemas** (API contracts)
- Its **service** (business logic — no DB calls in routers)
- Its **repository** (data access pattern, injected via DI)

Domains communicate via **service interfaces**, never by importing models from other domains directly.

### LLM Router Implementation

```python
# backend/ai/router.py

from backend.ai.providers.base import LLMProvider
from backend.ai.providers.openai_provider import OpenAIProvider
from backend.ai.providers.gemini_provider import GeminiProvider
from backend.billing.service import get_user_plan_tier
from backend.core.redis import redis_client
import asyncio, json

class LLMRouter:
    """
    Routes requests to the appropriate LLM provider based on:
    - User subscription tier
    - Provider availability / latency
    - Cost budget per request
    - Fallback chain on failure
    """

    def __init__(self):
        self.providers: dict[str, LLMProvider] = {
            "openai": OpenAIProvider(),
            "gemini": GeminiProvider(),
        }
        self.fallback_chain = ["openai", "gemini"]

    async def route(
        self,
        prompt: str,
        user_id: str,
        stream: bool = True,
    ):
        tier = await get_user_plan_tier(user_id)
        provider_name = self._select_provider(tier)

        for name in [provider_name] + [
            p for p in self.fallback_chain if p != provider_name
        ]:
            try:
                provider = self.providers[name]
                response = await provider.complete(prompt, stream=stream)
                await self._track_usage(user_id, name, prompt)
                return response
            except Exception as e:
                continue  # fallback to next

        raise RuntimeError("All LLM providers failed")

    def _select_provider(self, tier: str) -> str:
        return "openai" if tier in ("pro", "enterprise") else "gemini"

    async def _track_usage(self, user_id: str, provider: str, prompt: str):
        key = f"usage:{user_id}:{provider}"
        await redis_client.incr(key)
        await redis_client.expire(key, 86400)  # 24h window
```

### Resume Context Engine

```python
# backend/resume/context_engine.py

class ResumeContextEngine:
    """
    Enriches LLM prompts with personalized resume context.
    Matches the detected interview question type to relevant
    resume sections to generate personalized answer coaching.
    """

    async def build_context(
        self,
        question: str,
        user_id: str,
        resume_data: dict,
    ) -> str:
        question_type = self._classify_question(question)
        relevant_sections = self._extract_relevant_sections(
            question_type, resume_data
        )
        return self._format_context_block(relevant_sections)

    def _classify_question(self, question: str) -> str:
        behavioral_kw = ["tell me about", "describe a time", "how did you"]
        technical_kw  = ["explain", "how does", "what is", "implement"]
        if any(kw in question.lower() for kw in behavioral_kw):
            return "behavioral"
        if any(kw in question.lower() for kw in technical_kw):
            return "technical"
        return "general"

    def _extract_relevant_sections(
        self, question_type: str, resume_data: dict
    ) -> dict:
        if question_type == "behavioral":
            return {
                "experience": resume_data.get("experience", []),
                "projects":   resume_data.get("projects", []),
            }
        if question_type == "technical":
            return {
                "skills":  resume_data.get("skills", []),
                "projects": resume_data.get("projects", []),
            }
        return resume_data
```

---

## 4. Database Schema

```sql
-- ==========================================
-- USERS
-- ==========================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255),
    plan_tier       VARCHAR(50) DEFAULT 'free',   -- free | pro | enterprise
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    is_active       BOOLEAN DEFAULT TRUE,
    is_verified     BOOLEAN DEFAULT FALSE
);

-- ==========================================
-- RESUMES
-- ==========================================
CREATE TABLE resumes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    filename    VARCHAR(255),
    storage_key      VARCHAR(500),
    parsed_data JSONB,               -- structured JSON of resume content
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================
-- SESSIONS
-- ==========================================
CREATE TABLE sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    resume_id       UUID REFERENCES resumes(id),
    mode            VARCHAR(50) NOT NULL,   -- practice | interview | review
    title           VARCHAR(255),
    target_role     VARCHAR(255),
    target_company  VARCHAR(255),
    status          VARCHAR(50) DEFAULT 'active',  -- active | completed | abandoned
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    ended_at        TIMESTAMPTZ,
    duration_secs   INTEGER,
    total_questions INTEGER DEFAULT 0
);

-- ==========================================
-- TRANSCRIPTS
-- ==========================================
CREATE TABLE transcripts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID REFERENCES sessions(id) ON DELETE CASCADE,
    speaker         VARCHAR(50),             -- user | interviewer
    content         TEXT NOT NULL,
    confidence      FLOAT,                   -- Whisper confidence score
    language        VARCHAR(10) DEFAULT 'en',
    start_time_ms   BIGINT,
    end_time_ms     BIGINT,
    is_question     BOOLEAN DEFAULT FALSE,   -- detected as a question
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================
-- AI RESPONSES
-- ==========================================
CREATE TABLE ai_responses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID REFERENCES sessions(id) ON DELETE CASCADE,
    transcript_id   UUID REFERENCES transcripts(id),
    provider        VARCHAR(50),             -- openai | gemini
    model_name      VARCHAR(100),            -- gpt-4o | gemini-pro
    prompt_tokens   INTEGER,
    completion_tokens INTEGER,
    cost_usd        NUMERIC(10, 6),
    response_text   TEXT,
    response_type   VARCHAR(50),             -- suggestion | follow_up | feedback
    latency_ms      INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================
-- FEEDBACK & SCORING
-- ==========================================
CREATE TABLE session_feedback (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID REFERENCES sessions(id) ON DELETE CASCADE UNIQUE,
    overall_score       FLOAT,              -- 0.0 - 10.0
    communication_score FLOAT,
    technical_score     FLOAT,
    star_method_score   FLOAT,
    confidence_score    FLOAT,
    strengths           JSONB,              -- list of string strengths
    improvements        JSONB,              -- list of improvement areas
    detailed_report     TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================
-- SUBSCRIPTION PLANS
-- ==========================================
CREATE TABLE subscription_plans (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(100) UNIQUE NOT NULL,  -- free | pro | enterprise
    stripe_price_id     VARCHAR(255),
    price_usd_monthly   NUMERIC(10, 2),
    max_sessions_month  INTEGER,            -- NULL = unlimited
    max_duration_mins   INTEGER,            -- max session length
    llm_providers       JSONB,              -- ["gemini"] | ["openai","gemini"]
    features            JSONB,
    is_active           BOOLEAN DEFAULT TRUE
);

-- ==========================================
-- USER SUBSCRIPTIONS
-- ==========================================
CREATE TABLE user_subscriptions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE,
    plan_id             UUID REFERENCES subscription_plans(id),
    stripe_customer_id  VARCHAR(255),
    stripe_sub_id       VARCHAR(255),
    status              VARCHAR(50),        -- active | canceled | past_due
    current_period_start TIMESTAMPTZ,
    current_period_end   TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================
-- USAGE TRACKING
-- ==========================================
CREATE TABLE usage_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id  UUID REFERENCES sessions(id),
    event_type  VARCHAR(100),               -- session_start | ai_request | stt_seconds
    quantity    NUMERIC DEFAULT 1,
    metadata    JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================
-- ANALYTICS AGGREGATES (materialized daily)
-- ==========================================
CREATE TABLE analytics_daily (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    date            DATE NOT NULL,
    sessions_count  INTEGER DEFAULT 0,
    avg_score       FLOAT,
    total_mins      INTEGER,
    questions_asked INTEGER,
    ai_requests     INTEGER,
    UNIQUE(user_id, date)
);

-- INDEXES
CREATE INDEX idx_sessions_user_id     ON sessions(user_id);
CREATE INDEX idx_transcripts_session  ON transcripts(session_id);
CREATE INDEX idx_ai_responses_session ON ai_responses(session_id);
CREATE INDEX idx_usage_user_date      ON usage_events(user_id, created_at);
```

---

## 5. API Design

### REST Endpoints

```
AUTH
  POST   /api/v1/auth/register
  POST   /api/v1/auth/login
  POST   /api/v1/auth/refresh
  POST   /api/v1/auth/logout
  POST   /api/v1/auth/verify-email
  POST   /api/v1/auth/forgot-password
  POST   /api/v1/auth/reset-password

USERS
  GET    /api/v1/users/me
  PATCH  /api/v1/users/me
  DELETE /api/v1/users/me

RESUMES
  GET    /api/v1/resumes/
  POST   /api/v1/resumes/           ← multipart/form-data upload
  GET    /api/v1/resumes/{id}
  DELETE /api/v1/resumes/{id}
  POST   /api/v1/resumes/{id}/activate

SESSIONS
  GET    /api/v1/sessions/           ← paginated list
  POST   /api/v1/sessions/           ← create session
  GET    /api/v1/sessions/{id}
  PATCH  /api/v1/sessions/{id}
  DELETE /api/v1/sessions/{id}
  POST   /api/v1/sessions/{id}/end

TRANSCRIPTS
  GET    /api/v1/sessions/{id}/transcripts

FEEDBACK
  GET    /api/v1/sessions/{id}/feedback
  POST   /api/v1/sessions/{id}/feedback/generate

BILLING
  GET    /api/v1/billing/plans
  GET    /api/v1/billing/subscription
  POST   /api/v1/billing/checkout        ← create Stripe checkout session
  POST   /api/v1/billing/portal          ← Stripe customer portal
  POST   /api/v1/billing/webhook         ← Stripe webhook handler

ANALYTICS
  GET    /api/v1/analytics/dashboard
  GET    /api/v1/analytics/history?range=30d
  GET    /api/v1/analytics/scores
```

### WebSocket Events

```
CONNECTION
  ws://localhost:8000/ws/session/{session_id}?token={jwt}

CLIENT → SERVER Events:
  { "type": "audio_chunk",    "data": "<base64_pcm>", "seq": 1 }
  { "type": "session_pause" }
  { "type": "session_resume" }
  { "type": "session_end" }
  { "type": "ping" }

SERVER → CLIENT Events:
  { "type": "connected",      "session_id": "...", "timestamp": "..." }
  { "type": "transcript",     "text": "...", "is_final": false, "speaker": "user" }
  { "type": "transcript",     "text": "...", "is_final": true,  "speaker": "user" }
  { "type": "question_detected", "text": "Tell me about yourself..." }
  { "type": "ai_suggestion",  "token": "You could", "provider": "openai" }
  { "type": "ai_complete",    "full_text": "...", "response_id": "..." }
  { "type": "feedback_ready", "score": 8.2, "session_id": "..." }
  { "type": "error",          "code": "rate_limit", "message": "..." }
  { "type": "pong" }
```

### Authentication Flow

```
1. POST /auth/register → creates user, sends verification email
2. POST /auth/login    → returns {access_token (15min), refresh_token (7d)}
3. Every request       → Authorization: Bearer <access_token>
4. 401 received        → client sends refresh_token to /auth/refresh
5. New token pair      → client stores and retries
6. WS connection       → token passed as query param (secure over WSS)
```

### Rate Limiting Strategy

```python
# Applied per endpoint via Redis sliding window

RATE_LIMITS = {
    "auth":           {"requests": 10,   "window_secs": 60},
    "api_general":    {"requests": 100,  "window_secs": 60},
    "ai_suggestions": {"requests": 30,   "window_secs": 60},  # free tier
    "ai_suggestions_pro": {"requests": 200, "window_secs": 60},
    "resume_upload":  {"requests": 5,    "window_secs": 3600},
}
```

---

## 6. Frontend Architecture

### Component Hierarchy

```
App
├── AuthProvider (Zustand auth store)
├── Router
│   ├── /login          → <LoginPage />
│   ├── /register       → <RegisterPage />
│   ├── /dashboard      → <DashboardPage />
│   │   ├── <StatsOverview />
│   │   ├── <RecentSessions />
│   │   └── <ScoreChart />
│   ├── /practice       → <PracticeModePage />
│   │   ├── <ModeSelector />       (Practice | Interview)
│   │   ├── <ResumeSelector />
│   │   ├── <SessionConfig />
│   │   └── <StartButton />
│   ├── /session/:id    → <SessionPage />
│   │   ├── <AudioVisualizer />
│   │   ├── <TranscriptFeed />
│   │   ├── <AISuggestionPanel />
│   │   └── <SessionControls />
│   ├── /feedback/:id   → <FeedbackPage />
│   │   ├── <ScoreBreakdown />
│   │   ├── <TranscriptReview />
│   │   └── <ImprovementTips />
│   ├── /settings       → <SettingsPage />
│   │   ├── <ProfileSettings />
│   │   ├── <AudioSettings />
│   │   ├── <LLMSettings />
│   │   └── <BillingSettings />
│   └── /billing        → <BillingPage />
│       ├── <PlanCards />
│       └── <SubscriptionStatus />
└── OverlayWindow       → Separate Electron window (always-on-top)
    ├── <MiniTranscript />
    ├── <AISuggestionBubble />
    └── <SessionTimer />
```

### State Management (Zustand)

```typescript
// frontend/src/store/index.ts

interface AppState {
  // Auth
  user: User | null;
  token: string | null;
  login: (credentials: LoginPayload) => Promise<void>;
  logout: () => void;

  // Session
  session: Session | null;
  sessionStatus: "idle" | "active" | "paused" | "ended";
  transcripts: Transcript[];
  aiSuggestions: AISuggestion[];
  startSession: (config: SessionConfig) => Promise<void>;
  endSession: () => Promise<void>;

  // Audio
  isCapturing: boolean;
  audioLevel: number;
  toggleCapture: () => void;

  // UI
  overlayVisible: boolean;
  theme: "dark" | "light";
  toggleOverlay: () => void;
}
```

### Dark Minimal UI Design System

```
Design tokens:
  Background:    #0A0A0F  (near-black)
  Surface:       #141420  (card/panel bg)
  Surface-2:     #1E1E2E  (elevated surface)
  Border:        #2D2D3D
  Text-primary:  #E8E8F0
  Text-muted:    #7777AA
  Accent:        #6C63FF  (purple — focus, CTA)
  Success:       #22C55E
  Warning:       #F59E0B
  Error:         #EF4444
  
  Font: Inter (system UI fallback)
  Radius: 8px standard, 12px cards
  Shadow: 0 4px 24px rgba(108,99,255,0.15)
```

### Interview Mode vs Practice Mode

| Feature | Practice Mode | Interview Mode |
|---------|---------------|----------------|
| AI suggestions | Verbose coaching | Concise bullets |
| Transcript display | Full editor view | Minimal overlay |
| Post-session | Detailed analytics | Quick score card |
| Audio capture | Mic only | Mic + system |
| Session timer | Visible | Hidden |
| Hint overlay | Large panel | Compact bubble |

---

## 7. Electron Desktop Strategy

### Window Architecture

```
Main Process (Node.js / Electron)
├── main.ts                    ← app lifecycle, IPC handlers
├── windows/
│   ├── main-window.ts         ← primary dashboard window
│   └── overlay-window.ts      ← transparent always-on-top overlay
├── audio/
│   ├── wasapi-capture.ts      ← N-API binding to WASAPI
│   └── audio-stream.ts        ← stream management
└── ipc/
    └── handlers.ts            ← secure IPC bridge
```

### Transparent Overlay Window

```typescript
// electron/windows/overlay-window.ts

import { BrowserWindow, screen } from "electron";

export function createOverlayWindow(): BrowserWindow {
  const display = screen.getPrimaryDisplay();

  const overlay = new BrowserWindow({
    width: 420,
    height: 280,
    x: display.workAreaSize.width - 440,
    y: 20,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    focusable: false,       // does not intercept focus from meeting app
    resizable: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Exclude from screen capture (Windows 10+ SetWindowDisplayAffinity)
  overlay.setContentProtection(true);

  overlay.setAlwaysOnTop(true, "screen-saver", 1);
  overlay.loadURL(`${BASE_URL}/overlay`);

  return overlay;
}
```

### Hidden from Screen Share

`setContentProtection(true)` calls the Windows API `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` which prevents the window from appearing in:
- Zoom screen share
- Google Meet screen share
- Microsoft Teams screen share
- OBS / recording software

The overlay is visible only to the physical display — not to screen capture APIs.

### Secure IPC Communication

```typescript
// electron/preload.ts — exposed to renderer, NOT raw Node APIs
import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("electronAPI", {
  startAudioCapture: () => ipcRenderer.invoke("audio:start"),
  stopAudioCapture:  () => ipcRenderer.invoke("audio:stop"),
  getAudioDevices:   () => ipcRenderer.invoke("audio:devices"),
  onAudioChunk:      (cb: Function) => ipcRenderer.on("audio:chunk", (_, data) => cb(data)),
  openOverlay:       () => ipcRenderer.invoke("window:overlay:open"),
  closeOverlay:      () => ipcRenderer.invoke("window:overlay:close"),
  // No raw fs, no exec, no shell access exposed
});
```

### Auto-Start Meeting Detection

```typescript
// electron/main.ts — poll for active meeting processes
import { exec } from "child_process";

const MEETING_PROCESSES = ["Zoom.exe", "chrome.exe", "msedge.exe", "Teams.exe"];

function detectMeetingApp(): Promise<string | null> {
  return new Promise((resolve) => {
    exec("tasklist /fo csv /nh", (err, stdout) => {
      if (err) return resolve(null);
      for (const proc of MEETING_PROCESSES) {
        if (stdout.includes(proc)) return resolve(proc);
      }
      resolve(null);
    });
  });
}

setInterval(async () => {
  const meeting = await detectMeetingApp();
  if (meeting) {
    mainWindow.webContents.send("meeting:detected", meeting);
  }
}, 5000);
```

---

## 8. Multi-LLM Integration

### Provider Interface (Abstract Base)

```python
# backend/ai/providers/base.py

from abc import ABC, abstractmethod
from typing import AsyncGenerator

class LLMProvider(ABC):
    
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        stream: bool = True,
        max_tokens: int = 500,
    ) -> str | AsyncGenerator[str, None]:
        """Generate a completion. Supports streaming."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available."""
        ...

    @property
    @abstractmethod
    def cost_per_1k_tokens(self) -> float:
        """USD cost per 1000 tokens."""
        ...
```

### OpenAI Provider

```python
# backend/ai/providers/openai_provider.py

from openai import AsyncOpenAI
from .base import LLMProvider
from typing import AsyncGenerator

class OpenAIProvider(LLMProvider):
    
    def __init__(self):
        self.client = AsyncOpenAI()  # reads OPENAI_API_KEY from env
        self.model = "gpt-4o"

    async def complete(
        self,
        prompt: str,
        stream: bool = True,
        max_tokens: int = 500,
    ) -> AsyncGenerator[str, None]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system",  "content": SYSTEM_PROMPT},
                {"role": "user",    "content": prompt},
            ],
            max_tokens=max_tokens,
            stream=stream,
        )
        if stream:
            async def _stream():
                async for chunk in response:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
            return _stream()
        return response.choices[0].message.content

    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except:
            return False

    @property
    def cost_per_1k_tokens(self) -> float:
        return 0.005  # GPT-4o input pricing
```

### Gemini Provider

```python
# backend/ai/providers/gemini_provider.py

import google.generativeai as genai
from .base import LLMProvider
from typing import AsyncGenerator
import asyncio

class GeminiProvider(LLMProvider):

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel("gemini-1.5-pro")

    async def complete(
        self,
        prompt: str,
        stream: bool = True,
        max_tokens: int = 500,
    ) -> AsyncGenerator[str, None]:
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
        
        if stream:
            async def _stream():
                response = await asyncio.to_thread(
                    self.model.generate_content,
                    full_prompt,
                    stream=True,
                    generation_config={"max_output_tokens": max_tokens},
                )
                for chunk in response:
                    yield chunk.text
            return _stream()
        
        response = await asyncio.to_thread(
            self.model.generate_content, full_prompt
        )
        return response.text

    async def health_check(self) -> bool:
        try:
            await asyncio.to_thread(
                self.model.generate_content, "ping", 
                generation_config={"max_output_tokens": 5}
            )
            return True
        except:
            return False

    @property
    def cost_per_1k_tokens(self) -> float:
        return 0.00075  # Gemini 1.5 Pro pricing
```

### Fallback Logic & Response Ranking

```python
# backend/ai/response_ranker.py

class ResponseRanker:
    """
    Scores AI responses on quality dimensions.
    Used to select best response when multiple providers are tried.
    """

    def score(self, response: str, question: str) -> float:
        scores = {
            "length":      self._length_score(response),
            "structure":   self._structure_score(response),
            "relevance":   self._relevance_score(response, question),
            "actionable":  self._actionability_score(response),
        }
        weights = {"length": 0.2, "structure": 0.3, "relevance": 0.3, "actionable": 0.2}
        return sum(scores[k] * weights[k] for k in scores)

    def _length_score(self, text: str) -> float:
        words = len(text.split())
        if 80 <= words <= 300: return 1.0
        if 50 <= words < 80:   return 0.7
        return 0.4

    def _structure_score(self, text: str) -> float:
        markers = ["first", "second", "then", "finally", "for example",
                   "specifically", "as a result", "•", "-", "1.", "2."]
        found = sum(1 for m in markers if m in text.lower())
        return min(found / 3, 1.0)

    def _relevance_score(self, text: str, question: str) -> float:
        question_words = set(question.lower().split())
        response_words = set(text.lower().split())
        overlap = len(question_words & response_words)
        return min(overlap / max(len(question_words), 1), 1.0)

    def _actionability_score(self, text: str) -> float:
        action_words = ["you can", "consider", "practice", "focus on",
                        "improve", "recommend", "suggest", "try"]
        found = sum(1 for w in action_words if w in text.lower())
        return min(found / 2, 1.0)
```

---

## 9. Scalability Plan

### Capacity Model

| Users | Architecture | Infra |
|-------|-------------|-------|
| 0–100 | Single FastAPI + 1 DB | 1 VPS (4 vCPU, 8GB RAM) |
| 100–500 | Async workers + Redis | 2 VPS + managed PG |
| 500–2000 | Separate audio worker service | 3+ pods on K8s |
| 2000+ | Full microservices split | K8s + managed Redis + Aurora |

### Redis Caching Strategy

```python
# Cached items and TTLs:

USER_PLAN_TIER          → 300s   (5 min, invalidated on upgrade)
RESUME_PARSED_DATA      → 3600s  (1h, invalidated on re-upload)
SESSION_STATE           → 1800s  (30 min active session)
LLM_RESPONSE_CACHE      → 600s   (10 min, same question dedup)
RATE_LIMIT_COUNTERS     → window-based sliding (60s)
ANALYTICS_DAILY_AGGS    → 86400s (24h)
```

### Background Workers

```python
# workers/audio_worker.py — Celery or ARQ async tasks

@dramatiq.actor(queue_name="audio", max_retries=3)
async def process_audio_chunk(session_id: str, audio_b64: str, seq: int):
    """
    1. Decode base64 PCM audio
    2. Send to Whisper STT API
    3. Store transcript in DB
    4. Trigger LLM if question detected
    5. Stream response back via Redis pub/sub → WebSocket
    """
    ...

@dramatiq.actor(queue_name="feedback", max_retries=2)
async def generate_session_feedback(session_id: str):
    """
    Called after session ends.
    Analyzes full transcript, scores responses, stores feedback.
    """
    ...
```

### Streaming Optimization

- **Redis Pub/Sub** channels per session for WS → worker communication
- **Server-Sent Events** fallback if WebSocket is blocked (enterprise networks)
- **Chunked transfer encoding** for large AI responses
- **Audio compression**: Opus codec at 16kbps before sending over WS (reduces bandwidth 4x)

---

## 10. Security & Privacy

### Audio Data Handling

```
Audio flows:
  Client PCM → TLS 1.3 encryption → Server → Whisper API (HTTPS)
                                            → Immediate discard after STT
                                            → Transcript stored (encrypted at rest)

Audio is NEVER stored as a file. Raw PCM is processed in memory only.
Transcripts are encrypted using AES-256 at the database column level.
```

### JWT Best Practices

```python
ACCESS_TOKEN_EXPIRE_MINUTES  = 15    # short-lived
REFRESH_TOKEN_EXPIRE_DAYS    = 7     # long-lived, stored HttpOnly cookie
ALGORITHM                    = "RS256"  # asymmetric (private sign, public verify)
REFRESH_TOKEN_ROTATION       = True  # new refresh token on every refresh
REFRESH_TOKEN_FAMILY_TRACKING = True # invalidate all on reuse detection
```

### Secure API Key Storage

```
Server-side:
  - OPENAI_API_KEY, GEMINI_API_KEY → environment variables via Docker secrets
  - Never logged, never returned in API responses
  - Rotated via CI/CD pipeline secrets management (GitHub Actions secrets)

Client-side (Electron):
  - User JWT token stored in OS keychain (keytar library)
  - Never stored in localStorage or plaintext files
  - Cleared on logout
```

### Data Retention Policy

```
Active users:      transcripts retained for 90 days
Deleted accounts:  all data purged within 30 days
Audio raw data:    never stored (in-memory only)
Analytics:         aggregated data retained 1 year
User can:          download all data (GDPR) | delete all data
```

---

## 11. DevOps & Deployment

### Docker Compose (Development)

```yaml
# infra/docker-compose.dev.yml
version: "3.9"

services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/interviewcopilot
      - REDIS_URL=redis://redis:6379
    depends_on: [db, redis]
    volumes: ["./backend:/app"]
    command: uvicorn main:app --reload --host 0.0.0.0

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: interviewcopilot
    volumes: ["postgres_data:/var/lib/postgresql/data"]
    ports: ["5432:5432"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./infra/nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./infra/ssl:/etc/ssl
    depends_on: [backend]

volumes:
  postgres_data:
```

### Nginx Configuration

```nginx
# infra/nginx/nginx.conf

upstream backend {
    server backend:8000;
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name api.interviewcopilot.ai;

    ssl_certificate     /etc/ssl/cert.pem;
    ssl_certificate_key /etc/ssl/key.pem;

    # WebSocket support
    location /ws/ {
        proxy_pass         http://backend;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_read_timeout 3600s;  # hold WS for 1h max
    }

    location /api/ {
        proxy_pass       http://backend;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # Rate limiting
        limit_req zone=api burst=20 nodelay;
    }
}
```

### GitHub Actions CI/CD

```yaml
# .github/workflows/deploy.yml
name: Deploy InterviewCopilot AI

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install -r backend/requirements-dev.txt
      - run: pytest backend/tests/ --cov=backend --cov-report=xml
      - uses: codecov/codecov-action@v4

  build-backend:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}
      - uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: true
          tags: interviewcopilot/backend:${{ github.sha }}

  build-electron:
    needs: test
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: {node-version: "20"}
      - run: npm ci
        working-directory: ./electron
      - run: npm run build:win
        working-directory: ./electron
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - uses: actions/upload-artifact@v4
        with:
          name: windows-installer
          path: electron/dist/*.exe

  deploy:
    needs: [build-backend]
    runs-on: ubuntu-latest
    steps:
      - uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          key:  ${{ secrets.DEPLOY_KEY }}
          script: |
            cd /opt/interviewcopilot
            docker pull interviewcopilot/backend:${{ github.sha }}
            docker-compose up -d --no-deps backend
```

### Electron Builder (Windows Exe)

```json
// electron/package.json (build section)
{
  "build": {
    "appId": "ai.interviewcopilot.app",
    "productName": "InterviewCopilot AI",
    "win": {
      "target": ["nsis"],
      "icon": "assets/icon.ico",
      "requestedExecutionLevel": "asInvoker"
    },
    "nsis": {
      "oneClick": false,
      "allowToChangeInstallationDirectory": true,
      "installerIcon": "assets/installer.ico",
      "createDesktopShortcut": true,
      "createStartMenuShortcut": true
    },
    "publish": {
      "provider": "github",
      "owner": "your-org",
      "repo": "interviewcopilot-ai"
    }
  }
}
```

---

## 12. Monetization Strategy

### Plan Structure

| Feature | Free | Pro ($19/mo) | Enterprise ($49/mo) |
|---------|------|--------------|---------------------|
| Sessions/month | 5 | Unlimited | Unlimited |
| Max session length | 20 min | 90 min | 180 min |
| LLM provider | Gemini | GPT-4o + Gemini | GPT-4o + Gemini |
| AI suggestions | Basic | Advanced | Advanced + custom |
| Resume profiles | 1 | 5 | 20 |
| Analytics history | 7 days | 90 days | 1 year |
| Post-session report | Basic | Detailed | Detailed + export |
| Priority support | No | Email | Priority + Slack |
| Screen share safe | Yes | Yes | Yes + audit log |

### Stripe Integration

```python
# backend/billing/stripe_client.py

import stripe
from backend.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

async def create_checkout_session(
    user_id: str,
    plan_stripe_price_id: str,
    customer_email: str,
) -> str:
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        customer_email=customer_email,
        line_items=[{"price": plan_stripe_price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.FRONTEND_URL}/billing/cancel",
        metadata={"user_id": user_id},
        subscription_data={
            "trial_period_days": 7,  # 7-day free trial on Pro
            "metadata": {"user_id": user_id},
        },
    )
    return session.url


async def handle_webhook(payload: bytes, sig_header: str):
    event = stripe.Webhook.construct_event(
        payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )
    if event["type"] == "customer.subscription.updated":
        await _sync_subscription(event["data"]["object"])
    elif event["type"] == "customer.subscription.deleted":
        await _downgrade_to_free(event["data"]["object"])
    elif event["type"] == "invoice.payment_failed":
        await _notify_payment_failed(event["data"]["object"])
```

### Usage-Based Billing Add-ons (Enterprise)

```
Base plan:        flat monthly subscription
Overages:         $0.10 per AI request above 1000/month
                  $0.02 per STT minute above 300 min/month
Add-ons:          Custom question banks: $9/month
                  Team seats: $15/seat/month
                  API access: $29/month
```

---

## 13. 21-Day Development Roadmap

### Week 1 — Core Foundation (Days 1–7)

| Day | Task |
|-----|------|
| 1 | Repo setup, Docker Compose, FastAPI skeleton, DB migrations (Alembic) |
| 2 | Auth domain: register, login, JWT, refresh token rotation |
| 3 | User model, resume upload (S3), PDF parser (PyMuPDF) |
| 4 | Session model: CRUD endpoints, session state machine |
| 5 | React app scaffold: Tailwind, Zustand, routing, auth pages |
| 6 | Dashboard UI, session list, dark theme design system |
| 7 | Stripe integration: checkout, webhook, plan sync |

### Week 2 — AI + Streaming (Days 8–14)

| Day | Task |
|-----|------|
| 8  | WebSocket session handler, audio chunk receiver endpoint |
| 9  | Whisper STT integration, transcript storage |
| 10 | LLM Router: OpenAI provider + streaming token response |
| 11 | Gemini provider + fallback logic + response ranker |
| 12 | Resume context engine: question classification + enrichment |
| 13 | Prompt engineering: STAR method, behavioral, technical templates |
| 14 | Feedback engine: post-session scoring, analytics aggregation |

### Week 3 — Desktop + Polish (Days 15–21)

| Day | Task |
|-----|------|
| 15 | Electron main window + IPC bridge + preload secure API |
| 16 | WASAPI audio capture (N-API native module or node-wav), audio streaming |
| 17 | Overlay window: transparent, always-on-top, screen-share safe |
| 18 | Session UI: transcript feed, real-time AI suggestion panel |
| 19 | Feedback UI: score breakdown, improvement tips, charts |
| 20 | Electron Builder: Windows NSIS installer, auto-updater |
| 21 | End-to-end testing, performance profiling, staging deploy |

---

## 14. Resume-Ready Product Description

### For LinkedIn / Portfolio

> **InterviewCopilot AI** — AI-powered interview practice platform built as a production Windows desktop SaaS. Architected a full-stack system capturing real-time microphone and system audio via WASAPI loopback, streaming audio chunks over WebSockets to a FastAPI backend for near-real-time Whisper STT transcription and context-aware GPT-4o/Gemini coaching responses. Implemented a multi-LLM abstraction router with automatic fallback, cost tracking, and response quality ranking. Built a transparent Electron overlay window excluded from screen capture APIs. Designed a PostgreSQL schema covering users, sessions, transcripts, AI responses, subscriptions, and analytics. Integrated Stripe subscriptions with webhook-driven plan sync. Deployed via Docker + Nginx on VPS with GitHub Actions CI/CD producing signed Windows NSIS installers.

### Tech Stack Tags

`Python` `FastAPI` `PostgreSQL` `Redis` `WebSockets` `OpenAI API` `Gemini API` `React` `TailwindCSS` `Zustand` `Electron` `WASAPI` `Whisper STT` `Stripe` `Docker` `Nginx` `GitHub Actions` `JWT` `S3` `Alembic`

### Key Engineering Achievements

- Sub-800ms end-to-end latency from spoken word to AI coaching response
- Multi-LLM routing with automatic provider failover and cost-per-request tracking
- Windows WASAPI loopback system audio capture without virtual audio drivers
- Transparent overlay UI excluded from Zoom/Teams/Meet screen capture
- Modular monolith designed with clear domain boundaries for microservice extraction at scale
- JWT authentication with RS256, refresh token rotation, and OS keychain storage

---

*InterviewCopilot AI — Built for engineers who take their career seriously.*
