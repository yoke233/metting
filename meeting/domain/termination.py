"""Termination rules for meeting rounds."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TerminationConfig:
    # Thresholds that control early stop vs. max rounds.
    max_rounds: int = 6
    min_rounds: int = 1
    open_questions_max: int = 2
    disagreements_max: int = 1


# should_stop: decide whether to terminate the meeting loop.
def should_stop(
    round_index: int,
    artifacts_valid: bool,
    open_questions: int,
    disagreements: int,
    config: TerminationConfig,
) -> bool:
    # Stop on max rounds, valid artifacts, or low disagreement/questions.
    if round_index < config.min_rounds:
        return False
    if round_index >= config.max_rounds:
        return True
    if artifacts_valid:
        return True
    if open_questions <= config.open_questions_max and disagreements <= config.disagreements_max:
        return True
    return False


# metrics: emit convergence counters for event stream.
def metrics(
    open_questions: int,
    disagreements: int,
    consensus_score: float | None = None,
    vote_counts: dict | None = None,
) -> dict:
    # Emit lightweight convergence metrics to the event stream.
    payload = {
        "open_questions_count": open_questions,
        "disagreements_count": disagreements,
    }
    if consensus_score is not None:
        payload["consensus_score"] = consensus_score
    if vote_counts is not None:
        payload["vote_counts"] = vote_counts
    return payload
