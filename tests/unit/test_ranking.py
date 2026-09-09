from fip.strategy_library.ranking import rank_peer_group


def test_rank_peer_group_uses_average_rank_for_ties():
    result = rank_peer_group(((1, 80.0), (2, 80.0), (3, 60.0)), 3)
    assert [item.rank for item in result] == [1.5, 1.5, 3.0]
