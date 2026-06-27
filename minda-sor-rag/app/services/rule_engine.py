import json
import os
import re
from typing import Any


class RuleEngine:
    ESCAPE_CLAUSES = [
        "unless otherwise specified", "as far as practical", "where possible",
        "if resources permit", "to the extent feasible", "except where noted",
        "as agreed", "subject to", "wherever applicable",
        "to be revised after", "to be confirmed", "to be defined",
        "to be shared", "to be discussed", "to be finalized",
    ]
    PLACEHOLDERS = ["TBD", "TBS", "TBC", "TBA"]
    SUBJECTIVE_TERMS = [
        "objectionable", "easy", "adequate", "properly", "smoothly",
        "convenient", "harmony", "user-friendly", "friendly", "good",
    ]

    def __init__(self, weak_words_path: str | None = None):
        if weak_words_path is None:
            weak_words_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "knowledge_base", "weak_words.json"
            )
        with open(weak_words_path, "r") as f:
            self.WEAK_WORDS = json.load(f)

    def analyze(self, text: str) -> dict[str, Any]:
        ambiguous = self._check_ambiguity(text)
        escapes = self._check_escapes(text)
        placeholders = self._check_placeholders(text)
        passive = self._check_passive(text)
        atomic = self._check_atomic(text)
        verifiability = self._check_verifiable(text)
        negative = self._check_negative(text)

        return {
            "ambiguous_words": ambiguous,
            "escape_clauses": escapes,
            "placeholders": placeholders,
            "is_passive_voice": passive,
            "is_atomic": atomic,
            "verifiability": verifiability,
            "is_negative": negative,
            "quality_score": self._compute_score(
                ambiguous, escapes, placeholders, passive, atomic, verifiability, negative
            ),
            "violated_rules": self._get_violated_rules(
                ambiguous, escapes, placeholders, passive, atomic, verifiability, negative
            ),
            "suggested_action": self._suggest_action(
                ambiguous, escapes, placeholders, passive, atomic, verifiability, negative
            ),
        }

    def _check_ambiguity(self, text: str) -> list[str]:
        text_lower = text.lower()
        found = []
        for w in self.WEAK_WORDS:
            wl = w.lower()
            if " " in wl:
                if wl in text_lower:
                    found.append(w)
            else:
                if re.search(r"\b" + re.escape(wl) + r"\b", text_lower):
                    found.append(w)
        return found

    def _check_escapes(self, text: str) -> list[str]:
        text_lower = text.lower()
        return [e for e in self.ESCAPE_CLAUSES if e.lower() in text_lower]

    def _check_placeholders(self, text: str) -> list[str]:
        return [p for p in self.PLACEHOLDERS if re.search(r"\b" + p + r"\b", text, re.I)]

    def _check_passive(self, text: str) -> bool:
        patterns = [
            r"\b(is|are|was|were|be|been)\s+\w+ed\b",
            r"\b(is|are)\s+to\s+be\b",
        ]
        return any(re.search(p, text, re.I) for p in patterns)

    def _check_atomic(self, text: str) -> bool:
        shall_count = len(re.findall(r"\bshall\b", text, re.I))
        return shall_count <= 1

    def _check_verifiable(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in self.SUBJECTIVE_TERMS):
            return "FAIL"
        has_number = bool(re.search(r"\d+", text))
        has_unit = bool(
            re.search(
                r"(mm|cm|kg|°c|v\b|hz|db|ppm|%|sone|lux|years|km|cycles|passes|seconds|minutes|hours|n\b|ma|kΩ)",
                text,
                re.I,
            )
        )
        has_ref = bool(
            re.search(
                r"(as per|per std|standard|ais|iso|din|asme|cispr|eec|ece|fmvss|astm)",
                text,
                re.I,
            )
        )
        if has_number and (has_unit or has_ref):
            return "PASS"
        if has_ref:
            return "PASS"
        return "WARN"

    def _check_negative(self, text: str) -> bool:
        return bool(re.search(r"\b(shall|should|must)\s+not\b", text, re.I))

    def _compute_score(
        self,
        ambiguous: list[str],
        escapes: list[str],
        placeholders: list[str],
        passive: bool,
        atomic: bool,
        verifiability: str,
        negative: bool,
    ) -> int:
        s = 100
        s -= len(ambiguous) * 8
        s -= len(escapes) * 10
        s -= len(placeholders) * 15
        if passive:
            s -= 5
        if not atomic:
            s -= 15
        if verifiability == "FAIL":
            s -= 20
        elif verifiability == "WARN":
            s -= 10
        if negative:
            s -= 5
        return max(0, min(100, s))

    def _get_violated_rules(
        self,
        ambiguous: list[str],
        escapes: list[str],
        placeholders: list[str],
        passive: bool,
        atomic: bool,
        verifiability: str,
        negative: bool,
    ) -> list[str]:
        rules: list[str] = []
        if ambiguous:
            rules.append("R3")
        if escapes:
            rules.append("R10")
        if placeholders:
            rules.append("R4")
        if passive:
            rules.append("R2")
        if not atomic:
            rules.append("R5")
        if verifiability != "PASS":
            rules.append("R7")
        if negative:
            rules.append("R14")
        return rules

    def _suggest_action(
        self,
        ambiguous: list[str],
        escapes: list[str],
        placeholders: list[str],
        passive: bool,
        atomic: bool,
        verifiability: str,
        negative: bool,
    ) -> str:
        actions: list[str] = []
        if ambiguous:
            actions.append(f"Remove ambiguous terms: {', '.join(ambiguous[:3])}")
        if escapes:
            actions.append(f"Remove escape clause: {escapes[0]}")
        if placeholders:
            actions.append(f"Resolve placeholder: {placeholders[0]}")
        if passive:
            actions.append("Rewrite in active voice")
        if not atomic:
            actions.append("Split into separate requirements")
        if verifiability == "FAIL":
            actions.append("Add measurable acceptance criteria")
        elif verifiability == "WARN":
            actions.append("Consider adding quantitative criteria")
        if negative:
            actions.append("Rewrite as positive requirement")
        return "; ".join(actions) if actions else "No issues found"
