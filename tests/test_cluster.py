import pytest

from dddlint.cluster import clusters, similarities

pytestmark = pytest.mark.unit

RIGHT = [1.0, 0.0]
RIGHT_ISH = [0.96, 0.28]
UP = [0.0, 1.0]


def test_similarities_are_cosines_of_unit_vectors():
    matrix = similarities([RIGHT, UP, [2.0, 0.0]])
    assert matrix[0][0] == pytest.approx(1.0)
    assert matrix[0][1] == pytest.approx(0.0)
    assert matrix[0][2] == pytest.approx(1.0)


def test_similarities_tolerate_a_zero_vector():
    matrix = similarities([RIGHT, [0.0, 0.0]])
    assert matrix[1][1] == pytest.approx(0.0)


def test_clusters_group_above_threshold_only():
    assert clusters([RIGHT, RIGHT_ISH, UP], 0.9) == [[0, 1], [2]]
    assert clusters([RIGHT, RIGHT_ISH, UP], 0.99) == [[0], [1], [2]]


def test_clusters_link_transitively():
    chain = [RIGHT, RIGHT_ISH, [0.85, 0.53]]
    assert clusters(chain, 0.9) == [[0, 1, 2]]


def test_clusters_reject_a_threshold_outside_the_cosine_range():
    with pytest.raises(AssertionError, match="threshold"):
        clusters([RIGHT], 1.5)
