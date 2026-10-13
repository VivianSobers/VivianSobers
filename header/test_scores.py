import numpy as np
import pytest

from scores import (
    ROLES,
    check_causal,
    duplicate_token_score,
    first_token_score,
    induction_score,
    pick_heads,
    previous_token_score,
    score_all,
    spread_score,
)

N, PERIOD = 10, 5


def one_hot(targets):
    n = len(targets)
    pattern = np.zeros((n, n))
    pattern[np.arange(n), targets] = 1.0
    return pattern


def uniform_causal(n):
    return np.tril(np.ones((n, n))) / np.arange(1, n + 1)[:, None]


def induction_pattern():
    return one_hot([0] * PERIOD + [i - PERIOD + 1 for i in range(PERIOD, N)])


def duplicate_pattern():
    return one_hot([0] * PERIOD + [i - PERIOD for i in range(PERIOD, N)])


def test_first_token_score_is_one_when_every_query_reads_position_zero():
    assert first_token_score(one_hot([0] * N)) == pytest.approx(1.0)


def test_previous_token_score_is_one_for_offset_one_pattern():
    assert previous_token_score(one_hot([0] + list(range(N - 1)))) == pytest.approx(1.0)


def test_first_token_pattern_counts_only_position_one_as_previous_token():
    assert previous_token_score(one_hot([0] * N)) == pytest.approx(1 / (N - 1))


def test_induction_score_is_one_when_second_copy_reads_one_past_its_earlier_copy():
    assert induction_score(induction_pattern(), PERIOD) == pytest.approx(1.0)


def test_duplicate_token_score_is_one_when_second_copy_reads_its_earlier_copy():
    assert duplicate_token_score(duplicate_pattern(), PERIOD) == pytest.approx(1.0)


def test_induction_score_gives_no_credit_to_a_duplicate_token_pattern():
    assert induction_score(duplicate_pattern(), PERIOD) == pytest.approx(0.0)


def test_duplicate_token_score_gives_no_credit_to_an_induction_pattern():
    assert duplicate_token_score(induction_pattern(), PERIOD) == pytest.approx(0.0)


def test_spread_score_is_one_when_every_row_is_uniform_over_its_past():
    assert spread_score(uniform_causal(N)) == pytest.approx(1.0)


def test_spread_score_is_zero_when_every_row_is_one_hot():
    assert spread_score(one_hot([0] * N)) == pytest.approx(0.0)


def test_scores_broadcast_over_layers_and_heads():
    stack = np.broadcast_to(one_hot([0] * N), (2, 3, N, N))
    assert first_token_score(stack).shape == (2, 3)


def test_score_all_returns_a_layer_by_head_array_per_role():
    stack = np.broadcast_to(induction_pattern(), (2, 3, N, N))
    scores = score_all(stack, PERIOD)
    assert set(scores) == {"first_token", "previous_token", "duplicate_token", "induction", "spread"}
    assert scores["induction"] == pytest.approx(np.ones((2, 3)))


def test_pick_heads_takes_the_runner_up_when_the_best_head_is_already_used():
    scores = {role: np.zeros((2, 2)) for role in ROLES}
    scores["first_token"][0, 1] = 0.9
    scores["previous_token"][0, 1] = 0.8
    scores["previous_token"][1, 0] = 0.7
    scores["induction"][1, 1] = 0.6
    scores["spread"][0, 0] = 0.5
    assert pick_heads(scores) == [
        ("first_token", 0, 1),
        ("previous_token", 1, 0),
        ("induction", 1, 1),
        ("spread", 0, 0),
    ]


def test_check_causal_accepts_a_valid_pattern():
    check_causal(uniform_causal(N))


def test_check_causal_rejects_attention_to_future_positions():
    pattern = uniform_causal(N)
    pattern[2, 5] = 0.1
    with pytest.raises(ValueError, match="future"):
        check_causal(pattern)


def test_check_causal_rejects_rows_that_do_not_sum_to_one():
    with pytest.raises(ValueError, match="sum"):
        check_causal(uniform_causal(N) * 0.5)
