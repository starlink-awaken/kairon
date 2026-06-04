"""Tests for kairon_lib.weighted_voting — WeightedBallot, WeightedVoting."""

from kairon_lib.weighted_voting import WeightedBallot, WeightedVoting


class TestWeightedBallot:
    def test_ballot_creation(self):
        b = WeightedBallot(voter_id="v1", choice="yes", weight=2.0)
        assert b.voter_id == "v1"
        assert b.choice == "yes"
        assert b.weight == 2.0


class TestWeightedVoting:
    def test_set_voter_weight(self):
        wv = WeightedVoting()
        wv.set_voter_weight("v1", 3.0)
        assert wv._weights["v1"] == 3.0

    def test_cast_vote_with_default_weight(self):
        wv = WeightedVoting()
        wv.cast_weighted_vote("vote1", "v1", "yes")
        ballots = wv._ballots["vote1"]
        assert len(ballots) == 1
        assert ballots[0].weight == 1.0  # default

    def test_cast_vote_with_custom_weight(self):
        wv = WeightedVoting()
        wv.set_voter_weight("v1", 5.0)
        wv.cast_weighted_vote("vote1", "v1", "yes")
        ballots = wv._ballots["vote1"]
        assert ballots[0].weight == 5.0

    def test_tally_results(self):
        wv = WeightedVoting()
        wv.set_voter_weight("v1", 2.0)
        wv.set_voter_weight("v2", 3.0)
        wv.cast_weighted_vote("vote1", "v1", "yes")
        wv.cast_weighted_vote("vote1", "v2", "no")
        results = wv.tally_weighted_results("vote1")
        assert results["yes"] == 2.0
        assert results["no"] == 3.0

    def test_tally_nonexistent_vote(self):
        wv = WeightedVoting()
        results = wv.tally_weighted_results("nonexistent")
        assert results == {}

    def test_get_total_weight(self):
        wv = WeightedVoting()
        wv.set_voter_weight("v1", 1.0)
        wv.set_voter_weight("v2", 4.0)
        wv.cast_weighted_vote("vote1", "v1", "a")
        wv.cast_weighted_vote("vote1", "v2", "b")
        assert wv.get_total_weight("vote1") == 5.0

    def test_get_total_weight_nonexistent(self):
        wv = WeightedVoting()
        assert wv.get_total_weight("nonexistent") == 0.0

    def test_multiple_votes_same_voter_same_choice(self):
        """A voter can cast multiple votes for the same vote (no dedup)."""
        wv = WeightedVoting()
        wv.set_voter_weight("v1", 2.0)
        wv.cast_weighted_vote("vote1", "v1", "yes")
        wv.cast_weighted_vote("vote1", "v1", "yes")
        results = wv.tally_weighted_results("vote1")
        assert results["yes"] == 4.0  # 2 + 2
