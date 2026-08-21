"""Response quality ranker — scores AI responses for selection."""


class ResponseRanker:
    """
    Scores AI responses across four quality dimensions.
    Used to compare outputs between multiple providers.
    """

    WEIGHTS = {
        "length":      0.20,
        "structure":   0.30,
        "relevance":   0.30,
        "actionable":  0.20,
    }

    def score(self, response: str, question: str) -> float:
        scores = {
            "length":     self._length_score(response),
            "structure":  self._structure_score(response),
            "relevance":  self._relevance_score(response, question),
            "actionable": self._actionability_score(response),
        }
        return round(
            sum(scores[k] * self.WEIGHTS[k] for k in scores), 3
        )

    def _length_score(self, text: str) -> float:
        words = len(text.split())
        if 80 <= words <= 300:   return 1.0
        if 50 <= words < 80:     return 0.7
        if 300 < words <= 450:   return 0.7
        return 0.4

    def _structure_score(self, text: str) -> float:
        markers = [
            "first", "second", "third", "then", "finally", "for example",
            "specifically", "as a result", "•", "–", "-", "1.", "2.", "3.",
            "star", "situation", "task", "action", "result",
        ]
        found = sum(1 for m in markers if m in text.lower())
        return min(found / 4, 1.0)

    def _relevance_score(self, text: str, question: str) -> float:
        q_words = set(question.lower().split()) - {"the", "a", "an", "is", "was", "you", "me"}
        r_words = set(text.lower().split())
        overlap = len(q_words & r_words)
        return min(overlap / max(len(q_words), 1), 1.0)

    def _actionability_score(self, text: str) -> float:
        action_phrases = [
            "you can", "consider", "practice", "focus on", "improve",
            "recommend", "suggest", "try", "start by", "make sure",
            "avoid", "include", "emphasize", "highlight",
        ]
        found = sum(1 for p in action_phrases if p in text.lower())
        return min(found / 3, 1.0)

    def best(self, responses: list[tuple[str, str, str]]) -> tuple[str, str]:
        """
        Args:
            responses: list of (provider_name, response_text, question)
        Returns:
            (best_provider_name, best_response_text)
        """
        if not responses:
            raise ValueError("No responses to rank")
        scored = [
            (provider, text, self.score(text, question))
            for provider, text, question in responses
        ]
        scored.sort(key=lambda x: x[2], reverse=True)
        return scored[0][0], scored[0][1]
