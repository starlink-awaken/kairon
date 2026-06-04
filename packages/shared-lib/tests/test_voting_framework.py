"""Tests for kairon_lib.voting_framework — VoteType, Ballot, Vote, VotingFramework."""

import time

import pytest
from kairon_lib.voting_framework import Ballot, Vote, VoteType, VotingFramework


class TestVoteType:
    def test_enum_values(self):
        assert VoteType.SIMPLE_MAJORITY.value == "simple_majority"
        assert VoteType.SUPER_MAJORITY.value == "super_majority"
        assert VoteType.UNANIMOUS.value == "unanimous"
        assert VoteType.WEIGHTED.value == "weighted"


class TestBallot:
    def test_ballot_defaults(self):
        b = Ballot(ballot_id="b1", title="Test", vote_type=VoteType.SIMPLE_MAJORITY, options=["a", "b"])
        assert b.deadline is None
        assert b.min_voters == 1
        assert b.closed is False


class TestVote:
    def test_vote_default_weight(self):
        v = Vote(voter="v1", option="a")
        assert v.weight == 1.0


class TestVotingFramework:
    def test_create_ballot(self):
        vf = VotingFramework()
        ballot = vf.create_ballot("Pick one", ["x", "y"], VoteType.SIMPLE_MAJORITY)
        assert ballot.title == "Pick one"
        assert ballot.options == ["x", "y"]
        assert ballot.ballot_id.startswith("BALLOT-")

    def test_create_ballot_too_few_options(self):
        vf = VotingFramework()
        with pytest.raises(ValueError, match="at least 2 options"):
            vf.create_ballot("Bad", ["only"], VoteType.SIMPLE_MAJORITY)

    def test_cast_vote(self):
        vf = VotingFramework()
        b = vf.create_ballot("Pick", ["a", "b"], VoteType.SIMPLE_MAJORITY)
        vf.cast_vote(b.ballot_id, "voter1", "a")
        assert len(vf._votes[b.ballot_id]) == 1

    def test_cast_vote_duplicate_voter(self):
        vf = VotingFramework()
        b = vf.create_ballot("Pick", ["a", "b"], VoteType.SIMPLE_MAJORITY)
        vf.cast_vote(b.ballot_id, "v1", "a")
        with pytest.raises(ValueError, match="has already voted"):
            vf.cast_vote(b.ballot_id, "v1", "b")

    def test_cast_vote_invalid_option(self):
        vf = VotingFramework()
        b = vf.create_ballot("Pick", ["a", "b"], VoteType.SIMPLE_MAJORITY)
        with pytest.raises(ValueError, match="Invalid option"):
            vf.cast_vote(b.ballot_id, "v1", "c")

    def test_cast_vote_closed_ballot(self):
        vf = VotingFramework()
        b = vf.create_ballot("Pick", ["a", "b"], VoteType.SIMPLE_MAJORITY)
        vf.close_ballot(b.ballot_id)
        with pytest.raises(ValueError, match="closed"):
            vf.cast_vote(b.ballot_id, "v1", "a")

    def test_cast_vote_passed_deadline(self):
        vf = VotingFramework()
        b = vf.create_ballot("Pick", ["a", "b"], VoteType.SIMPLE_MAJORITY, deadline=time.time() - 10)
        with pytest.raises(ValueError, match="deadline"):
            vf.cast_vote(b.ballot_id, "v1", "a")

    def test_get_results_simple_majority(self):
        vf = VotingFramework()
        b = vf.create_ballot("Pick", ["a", "b"], VoteType.SIMPLE_MAJORITY)
        vf.cast_vote(b.ballot_id, "v1", "a")
        vf.cast_vote(b.ballot_id, "v2", "a")
        vf.cast_vote(b.ballot_id, "v3", "b")
        results = vf.get_results(b.ballot_id)
        assert results["a"] == 2.0
        assert results["b"] == 1.0

    def test_get_results_weighted(self):
        vf = VotingFramework()
        b = vf.create_ballot("Pick", ["a", "b"], VoteType.WEIGHTED)
        vf.cast_vote(b.ballot_id, "v1", "a", weight=3.0)
        vf.cast_vote(b.ballot_id, "v2", "b", weight=2.0)
        results = vf.get_results(b.ballot_id)
        assert results["a"] == 3.0
        assert results["b"] == 2.0

    def test_nonexistent_ballot(self):
        vf = VotingFramework()
        with pytest.raises(KeyError):
            vf.cast_vote("nonexistent", "v1", "a")

    def test_is_decided_simple_majority(self):
        vf = VotingFramework()
        b = vf.create_ballot("Pick", ["a", "b"], VoteType.SIMPLE_MAJORITY)
        assert vf.is_decided(b.ballot_id) is False
        vf.cast_vote(b.ballot_id, "v1", "a")
        vf.cast_vote(b.ballot_id, "v2", "b")
        # tie, not decided
        assert vf.is_decided(b.ballot_id) is False
        vf.cast_vote(b.ballot_id, "v3", "a")
        assert vf.is_decided(b.ballot_id) is True

    def test_is_decided_super_majority(self):
        vf = VotingFramework()
        b = vf.create_ballot("Pick", ["a", "b"], VoteType.SUPER_MAJORITY)
        vf.cast_vote(b.ballot_id, "v1", "a")
        vf.cast_vote(b.ballot_id, "v2", "a")
        vf.cast_vote(b.ballot_id, "v3", "b")
        # 2/3 = 66.7% >= 66.7%
        assert vf.is_decided(b.ballot_id) is True

    def test_is_decided_unanimous(self):
        vf = VotingFramework()
        b = vf.create_ballot("Pick", ["a", "b"], VoteType.UNANIMOUS)
        vf.cast_vote(b.ballot_id, "v1", "a")
        vf.cast_vote(b.ballot_id, "v2", "a")
        assert vf.is_decided(b.ballot_id) is True
        # With dissenting vote
        b2 = vf.create_ballot("Pick2", ["a", "b"], VoteType.UNANIMOUS)
        vf.cast_vote(b2.ballot_id, "v1", "a")
        vf.cast_vote(b2.ballot_id, "v2", "b")
        assert vf.is_decided(b2.ballot_id) is False

    def test_get_winner(self):
        vf = VotingFramework()
        b = vf.create_ballot("Pick", ["a", "b"], VoteType.SIMPLE_MAJORITY)
        assert vf.get_winner(b.ballot_id) is None  # Not decided yet
        vf.cast_vote(b.ballot_id, "v1", "a")
        vf.cast_vote(b.ballot_id, "v2", "a")
        assert vf.get_winner(b.ballot_id) == "a"

    def test_close_ballot(self):
        vf = VotingFramework()
        b = vf.create_ballot("Pick", ["a", "b"], VoteType.SIMPLE_MAJORITY)
        vf.cast_vote(b.ballot_id, "v1", "a")
        result = vf.close_ballot(b.ballot_id)
        assert b.closed is True
        assert result["ballot_id"] == b.ballot_id
        assert result["winner"] == "a"

    def test_list_ballots(self):
        vf = VotingFramework()
        b1 = vf.create_ballot("Vote1", ["a", "b"], VoteType.SIMPLE_MAJORITY)
        b2 = vf.create_ballot("Vote2", ["x", "y"], VoteType.SIMPLE_MAJORITY)
        all_ballots = vf.list_ballots()
        assert len(all_ballots) == 2
        vf.close_ballot(b1.ballot_id)
        open_ballots = vf.list_ballots(open_only=True)
        assert len(open_ballots) == 1
        assert open_ballots[0].ballot_id == b2.ballot_id
