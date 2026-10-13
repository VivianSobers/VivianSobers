"""Scores for the attention patterns the header shows. Each maps (..., N, N) to (...)."""

from __future__ import annotations

import numpy as np

ROLES = ("first_token", "previous_token", "induction", "spread")


def first_token_score(pattern: np.ndarray) -> np.ndarray:
    return pattern[..., 1:, 0].mean(axis=-1)


def previous_token_score(pattern: np.ndarray) -> np.ndarray:
    rows = np.arange(1, pattern.shape[-1])
    return pattern[..., rows, rows - 1].mean(axis=-1)


def _second_copy_score(pattern: np.ndarray, period: int, back: int) -> np.ndarray:
    rows = np.arange(period, pattern.shape[-1])
    return pattern[..., rows, rows - back].mean(axis=-1)


def duplicate_token_score(pattern: np.ndarray, period: int) -> np.ndarray:
    return _second_copy_score(pattern, period, back=period)


def induction_score(pattern: np.ndarray, period: int) -> np.ndarray:
    return _second_copy_score(pattern, period, back=period - 1)


def spread_score(pattern: np.ndarray) -> np.ndarray:
    """Mean normalised entropy of each row over the positions it may attend to (rows 1 onward)."""
    n = pattern.shape[-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(pattern > 0, -pattern * np.log(pattern), 0.0)
    entropy = terms[..., 1:, :].sum(axis=-1)
    return (entropy / np.log(np.arange(2, n + 1))).mean(axis=-1)


def check_causal(pattern: np.ndarray, atol: float = 1e-4) -> None:
    n = pattern.shape[-1]
    future = np.triu(np.ones((n, n), dtype=bool), k=1)
    if np.abs(pattern[..., future]).max() > atol:
        raise ValueError("attention reaches future positions")
    if np.abs(pattern.sum(axis=-1) - 1).max() > atol:
        raise ValueError("attention rows do not sum to one")


def score_all(attentions: np.ndarray, period: int) -> dict[str, np.ndarray]:
    return {
        "first_token": first_token_score(attentions),
        "previous_token": previous_token_score(attentions),
        "duplicate_token": duplicate_token_score(attentions, period),
        "induction": induction_score(attentions, period),
        "spread": spread_score(attentions),
    }


def pick_heads(scores: dict[str, np.ndarray], roles: tuple[str, ...] = ROLES) -> list[tuple[str, int, int]]:
    """Best head per role, in role order, never reusing a head an earlier role took."""
    used: set[tuple[int, int]] = set()
    picks = []
    for role in roles:
        values = scores[role]
        for flat in np.argsort(values, axis=None, kind="stable")[::-1]:
            layer, head = (int(k) for k in np.unravel_index(flat, values.shape))
            if (layer, head) not in used:
                break
        used.add((layer, head))
        picks.append((role, layer, head))
    return picks
