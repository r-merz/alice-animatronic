from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import json 
import ollama 

MODEL_NAME = "llama3.1"


# ---------------------------------------------------------
# Core state objects
# ---------------------------------------------------------


@dataclass
class EmotionalContext:
    possible_states: dict[str, float] = field(default_factory=dict)
    intensity: float = 0.0
    immediate_need: str | None = None
    problem_solving_readiness: float = 0.5
    confidence: float = 0.0


@dataclass
class ClinicalHypothesis:
    name: str
    confidence: float = 0.0

    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)

    last_updated: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class SafetyAssessment:
    level: str = "normal"
    concerns: list[str] = field(default_factory=list)
    requires_override: bool = False


@dataclass
class SupportStrategy:
    primary: str = "EXPLORE"
    secondary: list[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class SupportState:
    emotional_context: EmotionalContext
    safety: SafetyAssessment
    clinical_hypotheses: list[ClinicalHypothesis]
    strategy: SupportStrategy

    relevant_memories: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------
# Support loop
# ---------------------------------------------------------


class AliceSupportLoop:

    def __init__(self):
        self.previous_state: SupportState | None = None
        self.previous_user_message: str | None = None
        self.previous_response: str | None = None

    # -----------------------------------------------------
    # Public entry point
    # -----------------------------------------------------

    def process(
        self,
        user_message: str,
        relevant_memories: list[dict[str, Any]] | None = None,
    ) -> SupportState:

        memories = relevant_memories or []

        emotional_context = self.assess_emotional_context(
            user_message,
            memories,
        )

        safety = self.assess_safety(
            user_message,
            memories,
        )

        hypotheses = self.update_clinical_hypotheses(
            user_message,
            memories,
            emotional_context,
        )

        strategy = self.choose_support_strategy(
            user_message=user_message,
            emotional_context=emotional_context,
            safety=safety,
            hypotheses=hypotheses,
            memories=memories,
        )

        state = SupportState(
            emotional_context=emotional_context,
            safety=safety,
            clinical_hypotheses=hypotheses,
            strategy=strategy,
            relevant_memories=memories,
        )

        self.previous_user_message = user_message
        self.previous_state = state

        return state

    # -----------------------------------------------------
    # Emotional understanding
    # -----------------------------------------------------

    def assess_emotional_context(
        self,
        user_message: str,
        memories: list[dict[str, Any]],
    ) -> EmotionalContext:

        memory_context = memories[-5:]

        prompt = f"""
    Analyze the user's current emotional context.

    User message:
    {user_message}

    Relevant prior therapeutic memories:
    {json.dumps(
        memory_context,
        ensure_ascii=False,
        indent=2,
    )}

    Your task is NOT to diagnose the user.

    Estimate only the emotional and conversational context
    needed to decide how Alice should support the user.

    Determine:

    1. Possible emotional states.
    2. Overall emotional intensity.
    3. What the user appears to need right now.
    4. Whether they appear ready for problem solving.
    5. How confident you are in this interpretation.

    IMPORTANT RULES:
    - Treat emotional states as hypotheses, not facts.
    - Do not diagnose mental disorders.
    - Do not infer sensitive facts that the user did not state.
    - Use the current message as the strongest evidence.
    - Memories may provide context but must not override the
    current message.
    - If the user's meaning is ambiguous, lower confidence.
    - Do not assume sadness, anxiety, anger, or distress merely
    because the topic is serious.
    - "immediate_need" should describe the conversational need,
    not a diagnosis.

    Useful immediate_need values include:
    - being_heard
    - emotional_validation
    - exploration
    - reassurance
    - problem_solving
    - decision_support
    - grounding
    - information
    - encouragement
    - clarification
    - unknown

    Return valid JSON only:

    {{
    "possible_states": {{
        "sadness": 0.0,
        "frustration": 0.0
    }},
    "intensity": 0.0,
    "immediate_need": "unknown",
    "problem_solving_readiness": 0.5,
    "confidence": 0.0
    }}

    All numerical values must be between 0.0 and 1.0.

    Only include emotional states that have meaningful evidence.
    """

        try:
            response = ollama.chat(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You analyze emotional context for "
                            "a supportive conversational assistant. "
                            "Do not diagnose the user. "
                            "Return valid JSON only."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                format="json",
                options={
                    "temperature": 0.1,
                    "num_predict": 250,
                    "num_ctx": 4096,
                },
            )

            raw_result = str(
                response.get(
                    "message",
                    {},
                ).get(
                    "content",
                    "",
                )
            ).strip()

            if not raw_result:
                raise ValueError(
                    "Emotional-context model returned "
                    "an empty response."
                )

            result = json.loads(
                raw_result
            )

            if not isinstance(
                result,
                dict,
            ):
                raise TypeError(
                    "Emotional-context result must "
                    "be a JSON object."
                )

            possible_states = result.get(
                "possible_states",
                {},
            )

            if not isinstance(
                possible_states,
                dict,
            ):
                possible_states = {}

            cleaned_states = {}

            for name, value in possible_states.items():
                name = str(
                    name or ""
                ).strip().lower()

                if not name:
                    continue

                try:
                    score = float(
                        value
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                score = max(
                    0.0,
                    min(
                        1.0,
                        score,
                    ),
                )

                if score < 0.15:
                    continue

                cleaned_states[
                    name
                ] = score

            def clamp_score(
                value,
                default=0.0,
            ):
                try:
                    value = float(
                        value
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    return default

                return max(
                    0.0,
                    min(
                        1.0,
                        value,
                    ),
                )

            immediate_need = str(
                result.get(
                    "immediate_need",
                    "unknown",
                )
            ).strip().lower()

            allowed_needs = {
                "being_heard",
                "emotional_validation",
                "exploration",
                "reassurance",
                "problem_solving",
                "decision_support",
                "grounding",
                "information",
                "encouragement",
                "clarification",
                "unknown",
            }

            if (
                immediate_need
                not in allowed_needs
            ):
                immediate_need = "unknown"

            return EmotionalContext(
                possible_states=(
                    cleaned_states
                ),
                intensity=clamp_score(
                    result.get(
                        "intensity",
                        0.0,
                    )
                ),
                immediate_need=(
                    immediate_need
                ),
                problem_solving_readiness=(
                    clamp_score(
                        result.get(
                            "problem_solving_readiness",
                            0.5,
                        ),
                        default=0.5,
                    )
                ),
                confidence=clamp_score(
                    result.get(
                        "confidence",
                        0.0,
                    )
                ),
            )

        except (
            ollama.ResponseError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            print(
                "Support emotional-context error:",
                f"{type(error).__name__}: "
                f"{error}",
            )

            return EmotionalContext(
                possible_states={},
                intensity=0.0,
                immediate_need="unknown",
                problem_solving_readiness=0.5,
                confidence=0.0,
            )

    # -----------------------------------------------------
    # Safety
    # -----------------------------------------------------

    def assess_safety(
        self,
        user_message: str,
        memories: list[dict[str, Any]],
    ) -> SafetyAssessment:

        # Deliberately conservative placeholder.
        #
        # We will build a dedicated safety classifier rather than
        # mixing safety logic into the conversational prompt.

        return SafetyAssessment(
            level="normal",
            concerns=[],
            requires_override=False,
        )

    # -----------------------------------------------------
    # Clinical reasoning
    # -----------------------------------------------------

    def update_clinical_hypotheses(
        self,
        user_message: str,
        memories: list[dict[str, Any]],
        emotional_context: EmotionalContext,
    ) -> list[ClinicalHypothesis]:

        # IMPORTANT:
        #
        # These are hypotheses, NOT established diagnoses.
        #
        # Alice may use them internally when selecting support
        # strategies, but should not automatically tell the user
        # they "have" a particular condition.

        return []

    # -----------------------------------------------------
    # Support strategy
    # -----------------------------------------------------

    def choose_support_strategy(
        self,
        user_message: str,
        emotional_context: EmotionalContext,
        safety: SafetyAssessment,
        hypotheses: list[ClinicalHypothesis],
        memories: list[dict[str, Any]],
    ) -> SupportStrategy:

        if safety.requires_override:
            return SupportStrategy(
                primary="SAFETY_RESPONSE",
                secondary=[],
                reasoning=(
                    "Safety concerns override the normal "
                    "support strategy."
                ),
            )

        need = str(
            emotional_context.immediate_need
            or "unknown"
        ).strip().lower()

        intensity = float(
            emotional_context.intensity
        )

        readiness = float(
            emotional_context.problem_solving_readiness
        )

        confidence = float(
            emotional_context.confidence
        )

        # -----------------------------------------------------
        # Low-confidence interpretation
        # -----------------------------------------------------

        if confidence < 0.35:
            return SupportStrategy(
                primary="CLARIFY",
                secondary=["REFLECT"],
                reasoning=(
                    "Alice is not confident enough in the "
                    "emotional interpretation to assume what "
                    "the user needs."
                ),
            )

        # -----------------------------------------------------
        # User mainly needs to be heard
        # -----------------------------------------------------

        if need == "being_heard":
            return SupportStrategy(
                primary="LISTEN",
                secondary=[
                    "REFLECT",
                    "VALIDATE",
                ],
                reasoning=(
                    "The user appears to need space to express "
                    "the situation rather than immediate advice."
                ),
            )

        # -----------------------------------------------------
        # Emotional validation
        # -----------------------------------------------------

        if need == "emotional_validation":
            return SupportStrategy(
                primary="VALIDATE",
                secondary=[
                    "REFLECT",
                    "EXPLORE",
                ],
                reasoning=(
                    "The user's immediate need appears to be "
                    "acknowledgment of their emotional experience."
                ),
            )

        # -----------------------------------------------------
        # Grounding
        # -----------------------------------------------------

        if (
            need == "grounding"
            or (
                intensity >= 0.85
                and readiness < 0.35
            )
        ):
            return SupportStrategy(
                primary="GROUND",
                secondary=[
                    "VALIDATE",
                    "LISTEN",
                ],
                reasoning=(
                    "Emotional intensity appears high while "
                    "problem-solving readiness appears low."
                ),
            )

        # -----------------------------------------------------
        # Problem solving
        # -----------------------------------------------------

        if need == "problem_solving":
            if readiness >= 0.55:
                return SupportStrategy(
                    primary="PROBLEM_SOLVE",
                    secondary=[
                        "CLARIFY",
                        "ENCOURAGE",
                    ],
                    reasoning=(
                        "The user appears to want practical help "
                        "and seems ready to work through options."
                    ),
                )

            return SupportStrategy(
                primary="REFLECT",
                secondary=[
                    "EXPLORE",
                    "VALIDATE",
                ],
                reasoning=(
                    "The user appears to want a solution, but "
                    "their current readiness for problem solving "
                    "appears limited."
                ),
            )

        # -----------------------------------------------------
        # Decision support
        # -----------------------------------------------------

        if need == "decision_support":
            return SupportStrategy(
                primary="DECISION_SUPPORT",
                secondary=[
                    "CLARIFY",
                    "EXPLORE",
                ],
                reasoning=(
                    "The user appears to be weighing choices "
                    "rather than simply seeking reassurance."
                ),
            )

        # -----------------------------------------------------
        # Reassurance
        # -----------------------------------------------------

        if need == "reassurance":
            return SupportStrategy(
                primary="REASSURE",
                secondary=[
                    "VALIDATE",
                    "EXPLORE",
                ],
                reasoning=(
                    "The user appears to be seeking reassurance "
                    "or emotional steadiness."
                ),
            )

        # -----------------------------------------------------
        # Encouragement
        # -----------------------------------------------------

        if need == "encouragement":
            return SupportStrategy(
                primary="ENCOURAGE",
                secondary=[
                    "VALIDATE",
                ],
                reasoning=(
                    "The user appears to benefit primarily from "
                    "supportive encouragement."
                ),
            )

        # -----------------------------------------------------
        # Information
        # -----------------------------------------------------

        if need == "information":
            return SupportStrategy(
                primary="INFORM",
                secondary=[],
                reasoning=(
                    "The user's primary need appears informational "
                    "rather than therapeutic."
                ),
            )

        # -----------------------------------------------------
        # Exploration
        # -----------------------------------------------------

        if need == "exploration":
            return SupportStrategy(
                primary="EXPLORE",
                secondary=[
                    "REFLECT",
                ],
                reasoning=(
                    "The user appears to be trying to understand "
                    "their own experience."
                ),
            )

        # -----------------------------------------------------
        # Clarification
        # -----------------------------------------------------

        if need == "clarification":
            return SupportStrategy(
                primary="CLARIFY",
                secondary=[
                    "REFLECT",
                ],
                reasoning=(
                    "More information is needed before choosing "
                    "a stronger therapeutic intervention."
                ),
            )

        # -----------------------------------------------------
        # General fallback
        # -----------------------------------------------------

        if intensity >= 0.65:
            return SupportStrategy(
                primary="REFLECT",
                secondary=[
                    "VALIDATE",
                    "EXPLORE",
                ],
                reasoning=(
                    "The emotional intensity appears meaningful, "
                    "but Alice cannot confidently identify a more "
                    "specific immediate need."
                ),
            )

        return SupportStrategy(
            primary="EXPLORE",
            secondary=[
                "REFLECT",
            ],
            reasoning=(
                "No strong intervention is indicated, so Alice "
                "should understand the situation before directing "
                "the conversation."
            ),
        )

    # -----------------------------------------------------
    # Diagnostic disclosure
    # -----------------------------------------------------

    def user_requested_diagnostic_opinion(
        self,
        user_message: str,
    ) -> bool:

        text = user_message.lower()

        diagnostic_phrases = (
            "do i have ",
            "could i have ",
            "do you think i have ",
            "am i depressed",
            "am i bipolar",
            "am i autistic",
            "do i have anxiety",
            "what disorder do i have",
            "what condition do i have",
            "diagnose me",
            "what's my diagnosis",
            "what is my diagnosis",
        )

        return any(
            phrase in text
            for phrase in diagnostic_phrases
        )

    def should_expose_clinical_hypotheses(
        self,
        user_message: str,
        safety: SafetyAssessment,
    ) -> bool:

        # Safety information is never hidden merely because
        # the user did not request a diagnosis.

        if safety.requires_override:
            return True

        return self.user_requested_diagnostic_opinion(
            user_message
        )

    # -----------------------------------------------------
    # Reflection
    # -----------------------------------------------------

    def record_response(
        self,
        response: str,
    ) -> None:

        self.previous_response = response

    def reflect_on_next_message(
        self,
        new_user_message: str,
    ) -> dict[str, Any]:

        if (
            self.previous_user_message is None
            or self.previous_response is None
            or self.previous_state is None
        ):
            return {}

        previous_strategy = (
            self.previous_state
            .strategy
            .primary
        )

        prompt = f"""
    Evaluate how the user responded to Alice's previous
    supportive response.

    Previous user message:
    {self.previous_user_message}

    Alice's response:
    {self.previous_response}

    Support strategy used:
    {previous_strategy}

    User's next message:
    {new_user_message}

    Your task is NOT to diagnose the user.

    Determine whether Alice's previous response appeared:

    - helpful
    - somewhat_helpful
    - neutral
    - somewhat_unhelpful
    - unhelpful
    - unclear

    Also determine:

    1. Did the user continue engaging with the topic?
    2. Did the user appear more willing to talk?
    3. Did Alice misunderstand the user's need?
    4. Should the same support strategy be preferred again?
    5. Is there anything worth remembering about what helped
    or did not help?

    IMPORTANT:
    - Do not treat politeness alone as evidence that the response helped.
    - Do not treat disagreement as pathology.
    - Do not infer emotional improvement unless the user's response
    provides evidence.
    - A short reply such as "okay" may simply be neutral.
    - Memory candidates should describe interaction patterns,
    not diagnoses or permanent personality traits.
    - If there is not enough evidence, return null for memory_candidate.

    Return valid JSON only:

    {{
    "outcome": "unclear",
    "continued_engagement": false,
    "increased_openness": false,
    "possible_misunderstanding": false,
    "reuse_strategy": false,
    "confidence": 0.0,
    "reasoning": "",
    "memory_candidate": null
    }}
    """

        try:
            response = ollama.chat(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Evaluate conversational support outcomes. "
                            "Be conservative and evidence-based. "
                            "Do not diagnose the user. "
                            "Return valid JSON only."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                format="json",
                options={
                    "temperature": 0.1,
                    "num_predict": 300,
                    "num_ctx": 4096,
                },
            )

            raw_result = str(
                response.get(
                    "message",
                    {},
                ).get(
                    "content",
                    "",
                )
            ).strip()

            if not raw_result:
                raise ValueError(
                    "Reflection model returned an empty response."
                )

            result = json.loads(
                raw_result
            )

            if not isinstance(
                result,
                dict,
            ):
                raise TypeError(
                    "Reflection result must be a JSON object."
                )

            allowed_outcomes = {
                "helpful",
                "somewhat_helpful",
                "neutral",
                "somewhat_unhelpful",
                "unhelpful",
                "unclear",
            }

            outcome = str(
                result.get(
                    "outcome",
                    "unclear",
                )
            ).strip().lower()

            if outcome not in allowed_outcomes:
                outcome = "unclear"

            try:
                confidence = float(
                    result.get(
                        "confidence",
                        0.0,
                    )
                )
            except (
                TypeError,
                ValueError,
            ):
                confidence = 0.0

            confidence = max(
                0.0,
                min(
                    1.0,
                    confidence,
                ),
            )

            memory_candidate = result.get(
                "memory_candidate"
            )

            if memory_candidate is not None:
                memory_candidate = str(
                    memory_candidate
                ).strip()

                if not memory_candidate:
                    memory_candidate = None

            return {
                "previous_user_message":
                    self.previous_user_message,

                "alice_response":
                    self.previous_response,

                "user_followup":
                    new_user_message,

                "support_strategy_used":
                    previous_strategy,

                "outcome":
                    outcome,

                "continued_engagement":
                    bool(
                        result.get(
                            "continued_engagement",
                            False,
                        )
                    ),

                "increased_openness":
                    bool(
                        result.get(
                            "increased_openness",
                            False,
                        )
                    ),

                "possible_misunderstanding":
                    bool(
                        result.get(
                            "possible_misunderstanding",
                            False,
                        )
                    ),

                "reuse_strategy":
                    bool(
                        result.get(
                            "reuse_strategy",
                            False,
                        )
                    ),

                "confidence":
                    confidence,

                "reasoning":
                    str(
                        result.get(
                            "reasoning",
                            "",
                        )
                    ).strip(),

                "memory_candidate":
                    memory_candidate,
            }

        except (
            ollama.ResponseError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:

            print(
                "Support reflection error:",
                f"{type(error).__name__}: {error}",
            )

            return {}

# if __name__ == "__main__":

#     support_loop = AliceSupportLoop()

#     test_messages = [
#         "I had a pretty good day today.",
#         "I'm really frustrated. Nothing I try is working.",
#         "I don't really know what I'm feeling.",
#         "I'm overwhelmed and I don't know where to start.",
#         "Can you explain how Python dictionaries work?",
#     ]

#     for message in test_messages:
#         print(
#             "\nUSER:",
#             message,
#         )

#         result = support_loop.process(
#             message
#         )

#         print(
#             "EMOTIONAL CONTEXT:"
#         )

#         print(
#             result.emotional_context
#         )

#         print(
#             "STRATEGY:"
#         )

#         print(
#             result.strategy
#         )