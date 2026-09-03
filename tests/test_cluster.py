import itertools
import math

import pytest

from dddlint.cluster import centroid, clusters, cut, dendrogram, nearest, project, similarities

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


def test_project_flattens_to_two_dimensions():
    points = project([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    assert [len(p) for p in points] == [2, 2, 2]


def test_project_preserves_planar_distances():
    plane = [[1.0, 0.0, 0.0, 0.0], [0.0, 2.0, 0.0, 0.0], [3.0, 3.0, 0.0, 0.0]]
    points = project(plane)
    for (i, a), (j, b) in itertools.combinations(enumerate(points), 2):
        before = math.dist(plane[i], plane[j])
        assert math.dist(a, b) == pytest.approx(before, abs=1e-6)


def test_project_places_a_lone_vector_at_the_origin():
    assert project([[4.0, 2.0]]) == [(0.0, 0.0)]


def test_centroid_is_the_unit_mean():
    assert centroid([[3.0, 0.0], [0.0, 3.0]]) == pytest.approx([0.5**0.5, 0.5**0.5])


def test_nearest_picks_the_closest_centroid():
    label, score = nearest(RIGHT, {"east": RIGHT_ISH, "north": UP})
    assert label == "east"
    assert score == pytest.approx(0.96)


TWO_GROUPS = [[1, 0], [0.99, 0.14], [0.98, 0.2], [0, 1], [0.14, 0.99], [0.2, 0.98]]


def test_dendrogram_has_one_fewer_merge_than_points():
    assert len(dendrogram(TWO_GROUPS)) == len(TWO_GROUPS) - 1


def test_cut_recovers_the_two_natural_groups():
    merges = dendrogram(TWO_GROUPS)
    assert cut(merges, len(TWO_GROUPS), 2) == [[0, 1, 2], [3, 4, 5]]


def test_cut_ranges_from_one_cluster_to_all_singletons():
    merges = dendrogram(TWO_GROUPS)
    assert cut(merges, len(TWO_GROUPS), 1) == [[0, 1, 2, 3, 4, 5]]
    assert cut(merges, len(TWO_GROUPS), 6) == [[i] for i in range(6)]


def test_dendrogram_of_one_point_is_empty():
    assert dendrogram([[1.0, 0.0]]) == []
    assert cut([], 1, 1) == [[0]]
