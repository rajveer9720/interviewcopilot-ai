"""
Feedback service — post-session scoring engine.

Analyzes the full session transcript and AI responses to produce:
- Overall performance score (0–10)
- Sub-scores: communication, technical depth, STAR usage, confidence
- Strengths list
- Improvement areas list
- Detailed written report (LLM-generated)
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.sessions.models import Session, Transcript, AIResponse
from backend.feedback.models import SessionFeedback
from backend.auth.models import User
from backend.ai.router import LLMRouter

logger = logging.getLogger(__name__)
llm_router = LLMRouter()


class FeedbackService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_feedback(self, session_id: str) -> SessionFeedback:
        # Load session and all transcripts
        session_result = await self.db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = session_result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {session_id} not found")

        transcripts_result = await self.db.execute(
            select(Transcript).where(Transcript.session_id == session_id).order_by(Transcript.created_at)
        )
        transcripts = transcripts_result.scalars().all()

        if not transcripts:
            logger.warning("No transcripts for session %s — skipping feedback", session_id)
            return None

        user = await self.db.scalar(select(User).where(User.id == session.user_id))
        plan_tier = user.plan_tier if user else "free"

        # Build transcript summary for analysis
        transcript_text = "\n".join([
            f"[{t.speaker or 'user'}]: {t.content}"
            for t in transcripts
        ])
        if all(t.speaker == "interviewer" for t in transcripts):
            answers = (await self.db.scalars(select(AIResponse).where(
                AIResponse.session_id == session.id).order_by(AIResponse.created_at))).all()
            transcript_text += "\nAI sample answers:\n" + "\n".join(a.response_text or "" for a in answers)
            transcript_text = ("Only interviewer audio was captured. Evaluate the AI sample answers, "
                "not the candidate's actual performance. Explicitly state this limitation in REPORT.\n" + transcript_text)

        # LLM-generated analysis
        prompt = self._build_feedback_prompt(transcript_text, session.target_role)
        logger.info("Feedback LLM request started: session=%s plan=%s", session_id, plan_tier)
        analysis_result, provider_name = await llm_router.route(
            prompt,
            str(session.user_id),
            stream=False,
            plan_tier=plan_tier,
        )
        analysis_text = analysis_result
        logger.info(
            "Feedback LLM response received: session=%s provider=%s chars=%d",
            session_id,
            provider_name,
            len(analysis_text or ""),
        )

        # Parse scores (simplified — in production use structured output / JSON mode)
        scores = self._parse_scores(analysis_text)

        # Upsert feedback
        existing = await self.db.execute(
            select(SessionFeedback).where(SessionFeedback.session_id == session_id)
        )
        feedback = existing.scalar_one_or_none()

        if not feedback:
            feedback = SessionFeedback(session_id=session_id)
            self.db.add(feedback)

        feedback.overall_score       = scores.get("overall", 6.0)
        feedback.communication_score = scores.get("communication", 6.0)
        feedback.technical_score     = scores.get("technical", 6.0)
        feedback.star_method_score   = scores.get("star", 6.0)
        feedback.confidence_score    = scores.get("confidence", 6.0)
        feedback.strengths           = scores.get("strengths", [])
        feedback.improvements        = scores.get("improvements", [])
        feedback.detailed_report     = analysis_text

        await self.db.flush()
        return feedback

    def _build_feedback_prompt(self, transcript: str, target_role: str | None) -> str:
        role_context = f"for the role of {target_role}" if target_role else ""
        return f"""
You are an expert technical interview coach. Analyze this mock interview transcript {role_context}
and provide a structured performance evaluation.

TRANSCRIPT:
{transcript[:4000]}  

Provide your analysis in this exact format:
OVERALL_SCORE: <number 0-10>
COMMUNICATION_SCORE: <number 0-10>
TECHNICAL_SCORE: <number 0-10>
STAR_SCORE: <number 0-10>
CONFIDENCE_SCORE: <number 0-10>
STRENGTHS: <comma-separated list of 2-3 strengths>
IMPROVEMENTS: <comma-separated list of 2-3 specific improvements>
REPORT: <2-3 paragraph detailed coaching report>
"""

    def _parse_scores(self, text: str) -> dict:
        """Extract scores from formatted LLM output."""
        result = {}
        lines = text.split("\n")
        strength_list = []
        improvement_list = []

        for line in lines:
            if line.startswith("OVERALL_SCORE:"):
                result["overall"] = self._extract_float(line)
            elif line.startswith("COMMUNICATION_SCORE:"):
                result["communication"] = self._extract_float(line)
            elif line.startswith("TECHNICAL_SCORE:"):
                result["technical"] = self._extract_float(line)
            elif line.startswith("STAR_SCORE:"):
                result["star"] = self._extract_float(line)
            elif line.startswith("CONFIDENCE_SCORE:"):
                result["confidence"] = self._extract_float(line)
            elif line.startswith("STRENGTHS:"):
                raw = line.split(":", 1)[-1].strip()
                strength_list = [s.strip() for s in raw.split(",")]
            elif line.startswith("IMPROVEMENTS:"):
                raw = line.split(":", 1)[-1].strip()
                improvement_list = [s.strip() for s in raw.split(",")]

        result["strengths"]    = strength_list
        result["improvements"] = improvement_list
        return result

    def _extract_float(self, line: str) -> float:
        try:
            return float(line.split(":")[-1].strip())
        except (ValueError, IndexError):
            return 6.0
