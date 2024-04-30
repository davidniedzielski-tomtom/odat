from abc import abstractmethod
from typing import Sequence, List, Tuple, Dict

from openlr import LocationReferencePoint
from openlr_dereferencer import DecoderObserver

from openlr_dereferencer.decoding.candidate import Candidate
from openlr_dereferencer.decoding.routes import PointOnLine, Route
from openlr_dereferencer.maps import Line


class CandidateCollector(DecoderObserver):
    def __init__(self):
        self.candidates: Dict[int, Tuple[LocationReferencePoint, Candidate]] = {}

    """Abstract class representing an observer to the OpenLR decoding process"""

    def on_candidate_found(self, lrp: LocationReferencePoint, candidate: Candidate):
        """Called by the decoder when it finds a candidate for a location reference point"""
        pass

    def on_candidate_rejected(
        self, lrp: LocationReferencePoint, candidate: Candidate, reason: str
    ):
        """Called by the decoder when a candidate for a location reference point is rejected"""
        pass

    def on_candidate_rejected_bearing(
        self,
        lrp: LocationReferencePoint,
        candidate: Candidate,
        bearing: float,
        bearing_diff: float,
        max_bearing_deviation: float,
    ):
        """
        Called by the decoder when a candidate for a location reference point is rejected due to excessive bearing difference
        """
        pass

    def on_candidate_score(
        self,
        lrp: LocationReferencePoint,
        candidate: PointOnLine,
        geo_score: float,
        fow_score: float,
        frc_score: float,
        bear_score: float,
        total_score: float,
    ):
        """
        Called by the decoder when a candidate for a location reference point is scored
        """
        pass

    def on_candidate_rejected_frc(
        self, lrp: LocationReferencePoint, candidate: Candidate, tolerated_frc: int
    ):
        """
        Called by the decoder when a candidate for a location reference point is rejected due to incompatible FRC
        """
        pass

    def on_no_candidates_found(self, lrp: LocationReferencePoint):
        """Called by the decoder when it finds no candidates for a location reference point"""
        pass

    def on_candidates_found(
        self, lrp: LocationReferencePoint, candidates: List[Candidate]
    ):
        """Called by the decoder when it finds no candidates for a location reference point"""
        pass

    def on_route_fail_length(
        self,
        from_lrp: LocationReferencePoint,
        to_lrp: LocationReferencePoint,
        from_candidate: Candidate,
        to_candidate: Candidate,
        route: Route,
        actual_length,
        min_length: float,
        max_len_float,
    ):
        """Called by the decoder when it finds no candidates for a location reference point"""
        pass

    def on_route_success(
        self,
        from_lrp: LocationReferencePoint,
        to_lrp: LocationReferencePoint,
        from_candidate: Candidate,
        to_candidate: Candidate,
        path: Sequence[Line],
    ):
        """Called after the decoder successfully finds a route between two candidate
        lines for successive location reference points"""
        pass

    def on_location_end_reached(
        self,
        from_lrp: LocationReferencePoint,
        from_index: int,
        from_candidate: Candidate,
        to_lrp: LocationReferencePoint,
        to_candidate: Candidate,
    ):
        """Called when a route is found from an LRP to the end of the location"""
        self.candidates[from_index] = (from_lrp, from_candidate)
        self.candidates[from_index+1] = (to_lrp, to_candidate)

    def on_route_fail(
        self,
        from_lrp: LocationReferencePoint,
        to_lrp: LocationReferencePoint,
        from_candidate: Candidate,
        to_candidate: Candidate,
        reason: str,
    ):
        """Called after the decoder fails to find a route between two candidate
        lines for successive location reference points"""
        pass

    def on_matching_fail(
        self,
        from_lrp: LocationReferencePoint,
        to_lrp: LocationReferencePoint,
        from_candidates: Sequence[Candidate],
        to_candidates: Sequence[Candidate],
        reason: str,
    ):
        """Called after none of the candidate pairs for two LRPs were matching.

        The only way of recovering is to go back and discard the last bit of
        the dereferenced line location, if possible."""
        pass
class ScoreCollector(DecoderObserver):
    def __init__(self):

        self.geo_score = 0.0
        self.fow_score = 0.0
        self.frc_score = 0.0
        self.bear_score = 0.0
        self.total_score = 0.0

    """Abstract class representing an observer to the OpenLR decoding process"""

    def on_candidate_found(self, lrp: LocationReferencePoint, candidate: Candidate):
        """Called by the decoder when it finds a candidate for a location reference point"""
        pass

    def on_candidate_rejected(
            self, lrp: LocationReferencePoint, candidate: Candidate, reason: str
    ):
        """Called by the decoder when a candidate for a location reference point is rejected"""
        pass

    def on_candidate_rejected_bearing(
            self,
            lrp: LocationReferencePoint,
            candidate: Candidate,
            bearing: float,
            bearing_diff: float,
            max_bearing_deviation: float,
    ):
        """
        Called by the decoder when a candidate for a location reference point is rejected due to excessive bearing difference
        """
        pass

    def on_candidate_score(
            self,
            lrp: LocationReferencePoint,
            candidate: PointOnLine,
            geo_score: float,
            fow_score: float,
            frc_score: float,
            bear_score: float,
            total_score: float,
    ):
        """
        Called by the decoder when a candidate for a location reference point is scored
        """
        self.geo_score = geo_score
        self.fow_score = fow_score
        self.frc_score = frc_score
        self.bear_score = bear_score
        self.total_score = total_score


    def on_candidate_rejected_frc(
            self, lrp: LocationReferencePoint, candidate: Candidate, tolerated_frc: int
    ):
        """
        Called by the decoder when a candidate for a location reference point is rejected due to incompatible FRC
        """
        pass

    def on_no_candidates_found(self, lrp: LocationReferencePoint):
        """Called by the decoder when it finds no candidates for a location reference point"""
        pass

    def on_candidates_found(
            self, lrp: LocationReferencePoint, candidates: List[Candidate]
    ):
        """Called by the decoder when it finds no candidates for a location reference point"""
        pass

    def on_route_fail_length(
            self,
            from_lrp: LocationReferencePoint,
            to_lrp: LocationReferencePoint,
            from_candidate: Candidate,
            to_candidate: Candidate,
            route: Route,
            actual_length,
            min_length: float,
            max_len_float,
    ):
        """Called by the decoder when it finds no candidates for a location reference point"""
        pass

    def on_route_success(
            self,
            from_lrp: LocationReferencePoint,
            to_lrp: LocationReferencePoint,
            from_candidate: Candidate,
            to_candidate: Candidate,
            path: Sequence[Line],
    ):
        """Called after the decoder successfully finds a route between two candidate
        lines for successive location reference points"""
        pass

    def on_location_end_reached(
            self,
            from_lrp: LocationReferencePoint,
            from_index: int,
            from_candidate: Candidate,
            to_lrp: LocationReferencePoint,
            to_candidate: Candidate,
    ):
        """Called when a route is found from an LRP to the end of the location"""
        pass

    def on_route_fail(
            self,
            from_lrp: LocationReferencePoint,
            to_lrp: LocationReferencePoint,
            from_candidate: Candidate,
            to_candidate: Candidate,
            reason: str,
    ):
        """Called after the decoder fails to find a route between two candidate
        lines for successive location reference points"""
        pass

    def on_matching_fail(
            self,
            from_lrp: LocationReferencePoint,
            to_lrp: LocationReferencePoint,
            from_candidates: Sequence[Candidate],
            to_candidates: Sequence[Candidate],
            reason: str,
    ):
        """Called after none of the candidate pairs for two LRPs were matching.

        The only way of recovering is to go back and discard the last bit of
        the dereferenced line location, if possible."""
        pass
