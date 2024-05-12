import logging
from typing import Tuple, Optional, List, cast

import geoutils
from geoutils import buffer_wgs84_geometry, split_line, GeoCoordinates
from openlr import LineLocationReference, LocationReferencePoint, binary_decode
from openlr_dereferencer.decoding.candidate import Candidate
from openlr_dereferencer.decoding.candidate_functions import make_candidates
from openlr_dereferencer.decoding.line_decoding import LineLocation
from pyproj.exceptions import GeodError
from shapely import LineString, Point, Polygon, intersection
from webtool.map_databases.tomtom_sqlite import TomTomMapReaderSQLite

from .analysis_observer import AnalysisObserver
from .analysis_result import AnalysisResult
from .buffer_reader import BufferReader
from .decoder_configs import (
    StrictConfig,
    AnyPath,
    IgnoreFRC,
    IgnoreFOW,
    IgnorePathLength,
    IgnoreBearing,
)
from .decoder_observer import CandidateCollector, ScoreCollector


class Analyzer:

    def __init__(
            self,
            map_reader: TomTomMapReaderSQLite,
            buffer_radius: int = 20,
            lrp_radius: int = 20,
            map_bounds: Optional[Polygon] = None,
    ):
        self.map_reader = map_reader
        self.buffer_radius = buffer_radius
        self.lrp_radius = lrp_radius
        self.map_bounds = map_bounds
        self.analysis_observer = None

    def determine_restricted_decoding_failure_cause(
            self,
            buffer_map_reader: BufferReader,
    ) -> AnalysisResult:
        """
        Given a BufferReader containing a map restricted to a buffer around an encoded location, determine why
        the location cannot be decoded to a pth that falls within the buffer.  The idea is to perform a series
        of decoding, each of which ignores a different attribute of the location reference until a path is found.
        The last attribute ignored is assumed to be the attribute that caused the failure.  The first decoding
        ignores all attributes and checks whether there any viable path through the buffer that connects the
        LRPs, obeying only road geometries and one-way directions.
        Args:
            buffer_map_reader: BufferReader containing a map restricted to a buffer around an encoded location

        Returns:
            AnalysisResult describing the cause of the failure

        """
        # We're here because we couldn't find a path in the restricted target map

        if not buffer_map_reader.match(config=AnyPath):
            if self.analysis_observer:
                self.analysis_observer.on_diagnose_any_path_fail()
            return AnalysisResult.MISSING_OR_MISCONFIGURED_ROAD

        if buffer_map_reader.match(config=IgnoreFRC):
            if self.analysis_observer:
                self.analysis_observer.on_diagnose_frc_fail()
            return AnalysisResult.FRC_MISMATCH

        if buffer_map_reader.match(config=IgnoreFOW):
            if self.analysis_observer:
                self.analysis_observer.on_diagnose_fow_fail()
            return AnalysisResult.FOW_MISMATCH

        if buffer_map_reader.match(config=IgnorePathLength):
            if self.analysis_observer:
                self.analysis_observer.on_diagnose_length_fail()
            return AnalysisResult.PATH_LENGTH_MISMATCH

        if buffer_map_reader.match(config=IgnoreBearing):
            if self.analysis_observer:
                self.analysis_observer.on_diagnose_bearing_fail()
            return AnalysisResult.BEARING_MISMATCH

        if self.analysis_observer:
            self.analysis_observer.on_diagnose_multiple_attributes_fail()
        return AnalysisResult.MULTIPLE_ATTRIBUTE_MISMATCHES
    @staticmethod
    def build_decoded_ls(decode_result: LineLocation) -> LineString:
        """
        Build a LineString from a decoded LineLocation.  If the decoded line has offsets, the LineString will be
        adjusted to reflect the offsets.  If the sum of the offsets is larger than the line, the offsets will be
        reduced to ensure that the line is at least 1 meter long.

        Args:
            decode_result: LineLocation resulting from match operation

        Returns:
            LineString representing the decoded location

        """
        ls: LineString = geoutils.join_lines([line.geometry for line in decode_result.lines])
        if decode_result.p_off > 0.0 or decode_result.n_off > 0.0:
            pos_off: float = decode_result.p_off
            neg_off: float = decode_result.n_off
            ls_length: float = sum([line.length for line in decode_result.lines])
            if ls_length - pos_off - neg_off < 1.0:
                # The decoded line is shorter than the sum of the offsets
                # Adjusts the offsets such that the line is at least 1 meter long
                additional_length: float = max((pos_off + neg_off - ls_length) / 2.0, 1.0)
                pos_off = max(pos_off - additional_length, 0)
                neg_off = max(neg_off - additional_length, 0)
            if pos_off > 0.0:
                _, front = split_line(ls, pos_off)
                if front is None:
                    return LineString([ls.coords[-1], ls.coords[-1]])
            else:
                front = ls
            if neg_off > 0.0:
                _, back = split_line(front.reverse(), neg_off)
                if back is None:
                    return LineString([front.coords[0], front.coords[0]])
                back = back.reverse()
            else:
                back = front
            return back
        else:
            return ls

    @staticmethod
    def adjust_locref(
            locref: LineLocationReference, ls: LineString
    ) -> LineLocationReference:
        """
        Adjust the location reference so that the entire location reference is within the buffer

        Args:
            ls: LineString resulting from source map decoding

        Returns: possibly modified location reference

        """
        if locref.poffs == 0.0 and locref.noffs == 0.0:
            # nothing to do
            return locref

        lrps: List[LocationReferencePoint] = locref.points

        if locref.poffs > 0.0:
            p = Point(lrps[1].lon, lrps[1].lat)
            pref, _ = geoutils.split_line_at_point(ls, p)
            dnp = geoutils.line_string_length(pref)
            bearing_point = geoutils.interpolate(
                [GeoCoordinates(c[0], c[1]) for c in pref.coords], 20
            )
            bearing = geoutils.bearing(
                GeoCoordinates(pref.coords[0][0], pref.coords[0][1]), bearing_point
            )
            lrps[0] = LocationReferencePoint(
                lon=pref.coords[0][0],
                lat=pref.coords[0][1],
                frc=lrps[0].frc,
                fow=lrps[0].fow,
                bear=int(bearing),
                lfrcnp=lrps[0].lfrcnp,
                dnp=int(dnp),
            )

        if locref.noffs > 0.0:
            p = Point(lrps[-2].lon, lrps[-2].lat)
            _, suff = geoutils.split_line_at_point(ls, p)
            dnp = geoutils.line_string_length(suff)
            bearing_point = geoutils.interpolate(
                [GeoCoordinates(c[0], c[1]) for c in suff.reverse().coords], 20
            )
            bearing = geoutils.bearing(
                GeoCoordinates(suff.coords[-1][0], suff.coords[-1][1]), bearing_point
            )

            lrps[-2] = LocationReferencePoint(
                lon=lrps[-2].lon,
                lat=lrps[-2].lat,
                frc=lrps[-2].frc,
                fow=lrps[-2].fow,
                bear=lrps[-2].bear,
                lfrcnp=lrps[-2].lfrcnp,
                dnp=int(dnp),
            )
            lrps[-1] = LocationReferencePoint(
                lon=suff.coords[-1][0],
                lat=suff.coords[-1][1],
                frc=lrps[-1].frc,
                fow=lrps[-1].fow,
                bear=int(bearing),
                lfrcnp=lrps[-1].lfrcnp,
                dnp=lrps[-1].dnp,
            )

        return LineLocationReference(points=lrps, poffs=0, noffs=0)


    def create_buffer_reader(
            self, loc_ref: LineLocationReference, buffered_ls: Polygon
    ) -> BufferReader:
        """
        Create a BufferReader instance for a given location reference and buffered LineString
        Args:
            loc_ref: LineLocationReference representing encoded location
            buffered_ls: polygonal buffer around the encoded location

        Returns:
            a newly constructed BufferReader instance

        """
        return BufferReader(
            buffer=buffered_ls,
            loc_ref=loc_ref,
            tomtom_map_reader=self.map_reader,
            lrp_radius=self.lrp_radius,
        )

    def match_location(
            self, locref: LineLocationReference
    ) -> Tuple[Optional[LineLocation], Optional[LineString], CandidateCollector] :
        """
        Match a LineLocationReference using this Analyzer's map reader
        Args:
            locref: LineLocation Reference to be decoded (matched)

        Returns:
            Tuple of LineLocation, decoded LineString, and CandidateCollector if the match was successful, or a
            MatchResult indicating the reason for failure

        """
        decoder_observer = CandidateCollector()
        location = self.map_reader.match_location(locref, observer=decoder_observer)
        if location is None:
            return None, None, decoder_observer
        decoded_ls = self.build_decoded_ls(location)
        return location, decoded_ls, decoder_observer

    def analyze(self, olr: str, ls: LineString, analysis_observer: AnalysisObserver = None) -> Tuple[str, AnalysisResult, float]:
        """
        Given an OpenLR code and a LineString representing the location it represents on the encoding map, determine
        whether the the code can be decoded on the target map in such a way that the decoded location fits within
        a buffer around the encoded location.  If the decoded location is completely within the buffer, then we can
        assume the encoded and decoded locations are similar enough to be considered a match.  If the decoding fails,
        if the decoded location does not fit within a buffer, perform a number of analyses to determine the cause of
        the failure.

        Args:
            olr: OpenLR string to be decoded
            ls: LineString representing the "intended" location on the source map
            analysis_observer: an optional AnalysisObserver that records events occurring during the analysis

        Returns:
            Tuple of OpenLR string, AnalysisResult describing the analysis result, and a float representing the
            percentage of the decoded location that is within the buffer

        """
        logging.debug("Beginning analysis of OpenLR %s", olr)
        self.analysis_observer = analysis_observer

        if self.analysis_observer:
            self.analysis_observer.on_analysis_start(olr, ls, self)

        if self.map_bounds and not self.map_bounds.covers(ls):
            if self.analysis_observer:
                self.analysis_observer.on_out_of_bounds()
            return olr, AnalysisResult.OUTSIDE_MAP_BOUNDS, 0.0

        t_loc_ref: LineLocationReference = binary_decode(olr)

        # ensure we're working with a LineLocationReference
        if not isinstance(t_loc_ref, LineLocationReference):
            if self.analysis_observer:
                self.analysis_observer.on_unsupported_location_type(t_loc_ref)
            return olr, AnalysisResult.UNSUPPORTED_LOCATION_TYPE, 0.0

        # narrow type of LocationReference
        encoded_loc_ref: LineLocationReference = cast(LineLocationReference, t_loc_ref)

        # construct a buffer around the encoded location's LineString
        buffered_ls: Polygon = buffer_wgs84_geometry(
            ls, Point(ls.coords[0]), self.buffer_radius
        )

        if self.analysis_observer:
            self.analysis_observer.on_buffer_construction(buffered_ls)

        # attempt an initial decoding on the full map
        match self.match_location(encoded_loc_ref):
            case (None, None, decoder_observer):
                # We weren't able to decode the location reference on the full map,
                # so create a buffer reader and try to determine failure cause
                if self.analysis_observer:
                    self.analysis_observer.on_initial_decoding_fail(decoder_observer)
                buffer_map_reader = self.create_buffer_reader(encoded_loc_ref, buffered_ls)
                return (
                    olr,
                    self.determine_restricted_decoding_failure_cause(buffer_map_reader),
                    0.0,
                )
            case (decoded_location, decoded_ls, decoder_observer):
                # Decoding on the full map was successful -- now check if the location
                # is completely within the buffer
                if self.analysis_observer:
                    self.analysis_observer.on_initial_decoding_ok(
                        decoded_location, decoded_ls, decoder_observer
                    )
                if buffered_ls.covers(decoded_ls):
                    if self.analysis_observer:
                        self.analysis_observer.on_ok()
                    # all good -- the location is completely covered by the buffer
                    return olr, AnalysisResult.OK, 1.0
                else:
                    # the location is not completely covered by the buffer,  Calculate
                    # the percentage covered and adjust the location reference if necessary
                    percentage_within_buffer = (
                            intersection(buffered_ls, decoded_ls).length / decoded_ls.length
                    )
                    if self.analysis_observer:
                        self.analysis_observer.on_decoded_ls_not_in_buffer(percentage_within_buffer)

                    if decoded_location.p_off > 0 or decoded_location.n_off > 0:
                        # the location reference has offsets, so create a new reference that
                        # falls completely within the buffer.
                        return (
                            olr,
                            self.adjust_locref_and_match(
                                encoded_loc_ref,
                                decoded_location,
                                decoded_ls,
                                buffered_ls,
                                decoder_observer,
                            ),
                            percentage_within_buffer,
                        )
                    else:
                        # no offsets, so determine why a location within the buffer wasn't chosen
                        return (
                            olr,
                            self.analyze_within_buffer(
                                encoded_loc_ref, decoded_location, buffered_ls, decoder_observer
                            ),
                            percentage_within_buffer,
                        )

    def adjust_locref_and_match(
            self,
            encoded_loc_ref: LineLocationReference,
            full_map_decoded_location: LineLocation,
            full_map_decoded_ls: LineString,
            buffered_ls: Polygon,
            decoder_observer: CandidateCollector,
    ) -> AnalysisResult:
        """
        The initial decoding worked, but the location wasn't within the buffer.  Additionally, the OpenLR
        location reference has offsets.  This means that the first or last LRP might have been placed on
        segments outside the buffer.  Regenerate the location reference so that all LRPs are within the
        buffer, and then decode on the full map to see if the adjusted location is within the buffer.

        Args:
            encoded_loc_ref: The encoded LineLocationReference
            full_map_decoded_location: LineLocation from the initial decoding on full map
            full_map_decoded_ls: LineString from the initial decoding on full map
            buffered_ls: Polygon around the LineString from the encoded_loc_ref
            decoder_observer: DecoderObserver from the initial decoding on full map

        Returns:
            AnalysisResult describing the result of the analysis

        """
        try:
            adj_loc_ref: LineLocationReference = self.adjust_locref(encoded_loc_ref, full_map_decoded_ls)
        except GeodError:
            if self.analysis_observer:
                self.analysis_observer.on_invalid_geometry()
            return AnalysisResult.INVALID_GEOMETRY
        # Try decoding the adjusted location reference on the full map
        match self.match_location(adj_loc_ref):
            case None, None, adj_decoder_observer:
                # we couldn't decode the adjusted location reference to a location on the full map.
                # Since the adjusted location was restricted to the buffer, create a buffer reader and
                # determine why a location within the buffer could not be found.
                if self.analysis_observer:
                    self.analysis_observer.on_adj_loc_ref_match_fail(adj_decoder_observer)
                buffer_map_reader = self.create_buffer_reader(encoded_loc_ref, buffered_ls)
                return self.determine_restricted_decoding_failure_cause(
                    buffer_map_reader
                )
            case (adj_loc, full_map_decoded_ls, adj_decoder_observer):
                # we decoded the adjusted loc_ref.  Was the location within the buffer?
                if self.analysis_observer:
                    self.analysis_observer.on_adj_loc_ref_match_success(
                        adj_loc, full_map_decoded_ls, adj_decoder_observer
                    )
                if buffered_ls.covers(full_map_decoded_ls):
                    # The location was completely within the buffer.  Now compare the LRP
                    # placements in the initial decoding and the adjusted decoding to see
                    # if and why they differ.
                    if self.analysis_observer:
                        self.analysis_observer.on_adj_loc_ref_within_buffer()
                    # the decoding of the adjusted locref is completely within the buffer,
                    # so try and determine why the original decoding wasn't
                    return self.compare_locations(
                        full_map_decoded_location,
                        decoder_observer,
                        adj_loc,
                        adj_decoder_observer,
                    )
                else:
                    # the decoding of the adjusted location on the full map wasn't completely within the
                    # buffer, so examine the network within the buffer to determine why a path wasn't found
                    # therein (as it was on the encoding map).
                    if self.analysis_observer:
                        self.analysis_observer.on_adj_loc_ref_outside_buffer()
                    return self.analyze_within_buffer(
                        adj_loc_ref, adj_loc, buffered_ls, adj_decoder_observer
                    )

    def analyze_within_buffer(
            self,
            loc_ref: LineLocationReference,
            loc: LineLocation,
            buffered_ls: Polygon,
            decoder_observer: CandidateCollector,
    ) -> AnalysisResult:
        """
        A location was found on the full map, but not within the buffer. Attempt to decode the location reference
        but restrict the map to the buffer.  If a path is found within the buffer, then compare LRP placements
        to see if they caused the issue.  If no path is found, then attempt a series of controlled decodings
        to determine why a path within the buffer cannot be found.

        Args:
            loc_ref: LineLocationReference that *should* be decode-able to a path within the buffer
            loc: the LineLocation that was decoded on the full map
            buffered_ls: Polygon representing the buffer around encoded LineString
            decoder_observer: Decoder observer from the full map decoding

        Returns:
            AnalysisResult describing the result of the analysis

        """

        # create a MapReader that is restricted to the network within the buffer
        buffer_map_reader = self.create_buffer_reader(loc_ref, buffered_ls)
        buffer_observer = CandidateCollector()

        # attempt a decoding using the buffer map reader
        buffer_loc = buffer_map_reader.match(
            config=StrictConfig, observer=buffer_observer
        )
        if buffer_loc:
            # we found a path within the buffer, so try and determine why we chose
            # a different path in the full map
            if self.analysis_observer:
                self.analysis_observer.on_match_within_buffer_ok(buffer_loc, buffer_observer)
            return self.compare_locations(
                loc,
                decoder_observer,
                buffer_loc,
                buffer_observer,
            )
        else:
            # we couldn't find a path within the buffer, so try and determine whether the issue
            # is due to missing roads, misconfigured roads, or attribution mismatches
            if self.analysis_observer:
                self.analysis_observer.on_match_within_buffer_fail(buffer_observer)
            return self.determine_restricted_decoding_failure_cause(buffer_map_reader)


    def diagnose_score(
            self,
            lrp: LocationReferencePoint,
            outside: Candidate,
            inside: Candidate,
            is_last: bool,
    ) -> AnalysisResult:
        """
        Given two candidates (one chosen on the full map, and other on the buffer map) and an LRP for which
        they were chosen, determine which LRP attribute caused the outside candidate to be scored higher
        than the inside candidate.

        Args:
            lrp: LocationReferencePoint for which the candidates were chosen
            outside: the candidate chosen for the LRP on the full map
            inside: the candidate chosen on the buffer map
            is_last: a boolean indicating whether the LRP is the last in the location reference

        Returns:
            AnalysisResult describing the result of the analysis

        """
        out_score_collector = ScoreCollector()
        list(
            make_candidates(
                lrp,
                outside.line,
                self.map_reader.config,
                out_score_collector,
                is_last,
                self.map_reader.geo_tool,
            )
        )
        in_score_collector = ScoreCollector()
        list(
            make_candidates(
                lrp,
                inside.line,
                self.map_reader.config,
                in_score_collector,
                is_last,
                self.map_reader.geo_tool,
            )
        )

        if in_score_collector.frc_reject:
            if self.analysis_observer:
                self.analysis_observer.on_diagnose_frc_reject(in_score_collector)
            return AnalysisResult.BETTER_FRC_FOUND

        if in_score_collector.bearing_reject:
            if self.analysis_observer:
                self.analysis_observer.on_diagnose_bearing_reject(in_score_collector)
            return AnalysisResult.BETTER_BEARING_FOUND

        if in_score_collector.score_reject:
            if self.analysis_observer:
                self.analysis_observer.on_diagnose_low_score_reject(in_score_collector)
            return AnalysisResult.BETTER_SCORE_FOUND

        components = [0.0, 0.0, 0.0, 0.0]
        components[0] = self.map_reader.config.geo_weight * (
                out_score_collector.geo_score - in_score_collector.geo_score
        )
        components[1] = self.map_reader.config.bear_weight * (
                out_score_collector.bearing_score - in_score_collector.bearing_score
        )
        components[2] = self.map_reader.config.frc_weight * (
                out_score_collector.frc_score - in_score_collector.frc_score
        )
        components[3] = self.map_reader.config.fow_weight * (
                out_score_collector.fow_score - in_score_collector.fow_score
        )

        match components.index(max(components)):
            case 0:
                if self.analysis_observer:
                    self.analysis_observer.on_diagnose_better_geolocation(components)
                return AnalysisResult.BETTER_GEOLOCATION_FOUND

            case 1:
                if self.analysis_observer:
                    self.analysis_observer.on_diagnose_better_bearing(components)
                return AnalysisResult.BETTER_BEARING_FOUND

            case 2:
                if self.analysis_observer:
                    self.analysis_observer.on_diagnose_better_frc(components)
                return AnalysisResult.BETTER_FRC_FOUND

            case 3:
                if self.analysis_observer:
                    self.analysis_observer.on_diagnose_better_fow(components)
                return AnalysisResult.BETTER_FOW_FOUND

    def compare_locations(
            self,
            outside_loc: LineLocation,
            outside_obs: CandidateCollector,
            inside_loc: LineLocation,
            inside_obs: CandidateCollector,
    ) -> AnalysisResult:
        """
        Compare the LRP placements recorded in two decodings: one on the full map and one on the buffer map. If
        the placements differ, determine which LRP attribute caused the LRP to be placed on the full map candidate
        rather than the buffer map candidate.

        Args:
            outside_loc: LineLocation from the full map decoding
            outside_obs: DecoderObserver from the full map decoding
            inside_loc: LineLocation from the buffer map decoding
            inside_obs: DecoderObserver from the buffer map decoding

        Returns:
            AnalysisResult describing the result of the analysis

        """
        assert len(outside_obs.candidates) == len(inside_obs.candidates)
        outside_pairs = [
            outside_obs.candidates[i] for i in sorted(outside_obs.candidates)
        ]
        inside_pairs = [inside_obs.candidates[i] for i in sorted(inside_obs.candidates)]

        # check if the first LRP was placed on the same line
        if (outside_pairs[0][1].line.line_id != inside_pairs[0][1].line.line_id) and (
                outside_pairs[0][1].line.end_node.node_id
                != inside_pairs[0][1].line.start_node.node_id
        ):
            if self.analysis_observer:
                self.analysis_observer.on_lrp_placement_difference(
                    0,
                    outside_pairs[0][0],
                    inside_pairs[0][1],
                    outside_pairs[0][1],
                )
            return self.diagnose_score(
                lrp=outside_pairs[0][0],
                outside=outside_pairs[0][1],
                inside=inside_pairs[0][1],
                is_last=False,
            )

        for index, (outside, inside) in enumerate(zip(
                outside_pairs[1:-1],
                inside_pairs[1:-1],
        ),1):
            assert outside[0] == inside[0]
            # check if the intermediate LRPs were placed on the same line
            if outside[1].line.line_id != inside[1].line.line_id:
                if self.analysis_observer:
                    self.analysis_observer.on_lrp_placement_difference(
                        index,
                        outside[0],
                        inside[1],
                        outside[1],
                    )
                return self.diagnose_score(
                    lrp=outside[0], outside=outside[1], inside=inside[1], is_last=False
                )

        # check if the last LRP was placed on the same line
        if (outside_pairs[-1][1].line.line_id != inside_pairs[-1][1].line.line_id) and (
                outside_pairs[-1][1].line.start_node.node_id
                != inside_pairs[-1][1].line.end_node.node_id
        ):
            if self.analysis_observer:
                self.analysis_observer.on_lrp_placement_difference(
                    len(outside_pairs) - 1,
                    outside_pairs[-1][0],
                    inside_pairs[-1][1],
                    outside_pairs[-1][1],
                )
            return self.diagnose_score(
                lrp=outside_pairs[-1][0],
                outside=outside_pairs[-1][1],
                inside=inside_pairs[-1][1],
                is_last=True,
            )
        if self.analysis_observer:
            self.analysis_observer.on_diagnose_alternate_sp()

        return AnalysisResult.ALTERNATE_SHORTEST_PATH
