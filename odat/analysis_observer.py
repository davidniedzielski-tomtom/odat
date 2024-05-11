from typing import Protocol, List

from openlr import LineLocationReference, LocationReferencePoint
from openlr_dereferencer import DecoderObserver
from openlr_dereferencer.decoding import LineLocation
from openlr_dereferencer.decoding.candidate import Candidate
from shapely import LineString, Polygon

from odat.decoder_observer import CandidateCollector, ScoreCollector


class AnalysisObserver(Protocol):

    def on_analysis_start(
            self, olr: str, encoded_ls: LineString, analyzer: "Analyzer"
    ) -> None:
        """
        Called when the analysis process starts.
        Args:
            olr: OpenLR code to be analyzed
            encoded_ls: LineString representing the encoded location
            analyzer: Analysis object
        """
        pass

    def on_initial_decoding_ok(self,
                               line_location: LineLocation,
                               decoded_ls: LineString,
                               decoder_observer: DecoderObserver) -> None:
        """
        Called when the initial decoding is successful.
        Args:
            decoded_ls: LineString representing the decoded location
            decoder_observer: DecoderObserver that accompanied the decoding

        """
        pass

    def on_initial_decoding_fail(self,
                                 decoder_observer: DecoderObserver) -> None:
        """
        Called when the initial decoding fails.
        Args:
            decoder_observer: DecoderObserver that accompanied the decoding
        """
        pass

    def on_buffer_construction(self, buffer: Polygon) -> None:
        """
        Called when a buffer around the encoded linestring is created
        Args:
            buffer: buffer polygon
        """
        pass

    def on_out_of_bounds(self) -> None:
        """
        Called when the analyzer determines that the encoded location is outside the map extent
        """
        pass

    def on_ok(self) -> None:
        """
        Called when the decoded location is completely within the buffer
        """
        pass

    def on_decoded_line_creation(self, decoded_ls: LineString) -> None:
        """
        Called when the decoded line is created from the LineLocation returned from decoding
        Args:
            decoded_ls:  LineString representing decoded location
        """
        pass

    def on_decoded_ls_not_in_buffer(self, percentage_in_buffer: float) -> None:
        """
        Called when the decoded LineString is not completely covered by the buffer
        """
        pass

    def on_decoded_ls_in_buffer(self) -> None:
        """
        Called when the decoded LineString is completely covered by the buffer
        """
        pass

    def on_adjusted_loc_ref_created(
            self, adjusted_loc_ref: LineLocationReference, pos_off: float, neg_off: float
    ) -> None:
        """
        Called when the ecoded location reference is adjusted to fit within the buffer
        Args:
            adjusted_loc_ref: adjusted location reference
            pos_off: the new positive offset
            neg_off: the new negative offset
        """
        pass

    def on_invalid_geometry(self) -> None:
        """
        Called when a PyProf og Geod exception is thrown during analysis
        """
        pass

    def on_adj_loc_ref_match_success(
            self,
            adj_loc: LineLocationReference,
            decoded_ls: LineString,
            observer: DecoderObserver,
    ) -> None:
        """
        Called when the adjusted location reference is successfully decoded against the full map
        Args:
            adj_loc: adjusted location reference
            decoded_ls: LineString representing the decoded location
            observer: DecoderObserver that accompanied the decoding
        """
        pass

    def on_adj_loc_ref_match_fail(self, decoding_observer: DecoderObserver) -> None:
        pass

    def on_match_within_buffer_ok(self, loc_ref: LineLocationReference, observer: DecoderObserver) -> None:
        pass

    def on_match_within_buffer_fail(self, observer: DecoderObserver) -> None:
        pass

    def on_adj_loc_ref_within_buffer(self) -> None:
        pass

    def on_adj_loc_ref_outside_buffer(self) -> None:
        pass

    def on_unsupported_location_type(self) -> None:
        """
        Called when the analyzer is passed an OpenLR code that is not a LineLocationReference
        """
        pass

    def on_diagnose_any_path_fail(self) -> None:
        pass

    def on_diagnose_frc_fail(self) -> None:
        pass
    def on_diagnose_fow_fail(self) -> None:
        pass

    def on_diagnose_length_fail(self) -> None:
        pass

    def on_diagnose_bearing_fail(self) -> None:
        pass

    def on_diagnose_multiple_attributes_fail(self) -> None:
        pass
    def on_diagnose_alternate_sp(self) -> None:
        pass

    def on_compare_location_start(
            self, inside: CandidateCollector, outside: CandidateCollector
    ) -> None:
        pass

    def on_lrp_placement_difference(
            self,
            index: int,
            lrp: LocationReferencePoint,
            inside: Candidate,
            outside: Candidate,
    ) -> None:
        pass

    def on_diagnose_frc_reject(self, collector: ScoreCollector) -> None:
        pass

    def on_diagnose_bearing_reject(self, collector: ScoreCollector) -> None:
        pass

    def on_diagnose_low_score_reject(self, collector: ScoreCollector) -> None:
        pass

    def on_diagnose_better_geolocation(self, components: List[float]) -> None:
        pass

    def on_diagnose_better_bearing(self, components: List[float]) -> None:
        pass

    def on_diagnose_better_frc(self, components: List[float]) -> None:
        pass

    def on_diagnose_better_fow(self, components: List[float]) -> None:
        pass

class AnalysisCollector(AnalysisObserver):
    def on_analysis_start(self, olr: str, encoded_ls: LineString, analyzer: "Analyzer") -> None:
        print("Analysis started")

    def on_initial_decoding_ok(self, line_location: LineLocation, decoded_ls: LineString,
                               decoder_observer: DecoderObserver) -> None:
        print("Initial decoding successful")

    def on_initial_decoding_fail(self, decoder_observer: DecoderObserver) -> None:
        print("Initial decoding failed")

    def on_buffer_construction(self, buffer: Polygon) -> None:
        print("Buffer constructed")

    def on_out_of_bounds(self) -> None:
        print("Out of bounds")

    def on_ok(self) -> None:
        print("OK")

    def on_decoded_line_creation(self, decoded_ls: LineString) -> None:
        print("Decoded line created")

    def on_decoded_ls_not_in_buffer(self, percentage_in_buffer: float) -> None:
        print("Decoded line not in buffer")

    def on_decoded_ls_in_buffer(self) -> None:
        print("Decoded line in buffer")

    def on_adjusted_loc_ref_created(self, adjusted_loc_ref: LineLocationReference, pos_off: float,
                                    neg_off: float) -> None:
        print("Adjusted location reference created")

    def on_invalid_geometry(self) -> None:
        print("Invalid geometry")

    def on_adj_loc_ref_match_success(self, adj_loc: LineLocationReference, decoded_ls: LineString,
                                     observer: DecoderObserver) -> None:
        print("Adjusted location reference match success")

    def on_adj_loc_ref_match_fail(self, decoding_observer: DecoderObserver) -> None:
        print("Adjusted location reference match fail")

    def on_match_within_buffer_ok(self, loc_ref: LineLocationReference, observer: DecoderObserver) -> None:
        print("Match within buffer OK")

    def on_match_within_buffer_fail(self, observer: DecoderObserver) -> None:
        print("Match within buffer fail")

    def on_adj_loc_ref_within_buffer(self) -> None:
        print("Adjusted location reference within buffer")

    def on_adj_loc_ref_outside_buffer(self) -> None:
        print("Adjusted location reference outside buffer")

    def on_unsupported_location_type(self) -> None:
        print("Unsupported location type")

    def on_diagnose_any_path_fail(self) -> None:
        print("Diagnose any path fail")

    def on_diagnose_frc_fail(self) -> None:
        print("Diagnose FRC fail")

    def on_diagnose_fow_fail(self) -> None:
        print("Diagnose FOW fail")

    def on_diagnose_length_fail(self) -> None:
        print("Diagnose length fail")

    def on_diagnose_bearing_fail(self) -> None:
        print("Diagnose bearing fail")

    def on_diagnose_multiple_attributes_fail(self) -> None:
        print("Diagnose multiple attributes fail")

    def on_diagnose_alternate_sp(self) -> None:
        print("Diagnose alternate SP")

    def on_compare_location_start(self, inside: CandidateCollector, outside: CandidateCollector) -> None:
        print("Compare location start")

    def on_lrp_placement_difference(self, index: int, lrp: LocationReferencePoint, inside: Candidate,
                                    outside: Candidate) -> None:
        print("LRP placement difference")

    def on_diagnose_frc_reject(self, collector: ScoreCollector) -> None:
        print("Diagnose FRC reject")

    def on_diagnose_bearing_reject(self, collector: ScoreCollector) -> None:
        print("Diagnose bearing reject")

    def on_diagnose_low_score_reject(self, collector: ScoreCollector) -> None:
        print("Diagnose low score reject")

    def on_diagnose_better_geolocation(self, components: List[float]) -> None:
        print("Diagnose better geolocation")

    def on_diagnose_better_bearing(self, components: List[float]) -> None:
        print("Diagnose better bearing")

    def on_diagnose_better_frc(self, components: List[float]) -> None:
        print("Diagnose better FRC")

    def on_diagnose_better_fow(self, components: List[float]) -> None:
        print("Diagnose better FOW")