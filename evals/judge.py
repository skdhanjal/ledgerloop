"""The judge, for the one thing with no objective answer: explanation quality.

Everything else in LedgerLoop is scored deterministically. A judge is a last
resort, and its scores are only reportable alongside its agreement rate.
"""
from typing import Literal

from pydantic import BaseModel, Field

from config import get_model

JUDGE_RUBRIC = """Score this accounts-payable exception explanation.

Score each criterion 1-5. Be strict: 5 means an experienced AP controller
would act on it without asking a follow-up question.

1. CORRECTNESS - does the stated root cause match the ground-truth defect?
2. GROUNDING   - is every figure and claim traceable to a tool result?
3. COMPLETENESS - does it explain ALL flagged exceptions, or stop at the first?
4. ACTIONABILITY - could a controller decide hold/approve/reject from this
   alone, without opening the invoice?

Quote the specific text that justifies each score. If you cannot quote
something, the score for that criterion is at most 3."""


class JudgeScore(BaseModel):
    correctness: int = Field(ge=1, le=5)
    grounding: int = Field(ge=1, le=5)
    completeness: int = Field(ge=1, le=5)
    actionability: int = Field(ge=1, le=5)
    justification: str = Field(description="Quote the text behind each score")

    @property
    def mean(self) -> float:
        return (self.correctness + self.grounding
                + self.completeness + self.actionability) / 4


def make_judge(model_name: str = "judge"):
    """NOTE the default tier: judge on a DIFFERENT model from the generator.

    A judge sharing a model with the generator rates that model's output
    higher (self-preference) - the same problem Day 17's reviewer had, for
    the same reason.
    """
    judge = get_model(model_name).with_structured_output(JudgeScore)

    def score(*, explanation: str, truth: dict, trajectory: list[dict]) -> JudgeScore:
        return judge.invoke([
            {"role": "system", "content": JUDGE_RUBRIC},
            {"role": "user", "content": (
                f"GROUND TRUTH DEFECT: {truth['seeded_exception']}\n"
                f"EXPECTED DECISION: {truth['expected_decision']}\n\n"
                f"TOOL RESULTS THE AGENT SAW:\n"
                + "\n".join(f"- {s['tool']}: {s['result'][:200]}"
                             for s in trajectory)
                + f"\n\nEXPLANATION UNDER REVIEW:\n{explanation}")},
        ])

    return score
