import logging
from typing import Tuple, Optional

import geoutils
from geoutils import buffer_wgs84_geometry, split_line, GeoCoordinates
from openlr import LineLocationReference, LocationReferencePoint, binary_decode
from openlr_dereferencer.decoding.candidate import Candidate
from openlr_dereferencer.decoding.candidate_functions import make_candidates
from openlr_dereferencer.decoding.line_decoding import LineLocation
from pyproj.exceptions import GeodError
from shapely import LineString, Point, Polygon, intersection
from webtool.map_databases.tomtom_sqlite import TomTomMapReaderSQLite

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
from .match_result import MatchResult
from .odat_observer import CandidateCollector, ScoreCollector


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
        if locref.poffs == 0 and locref.noffs == 0:
            return locref

        lrps = locref.points

        if locref.poffs > 0:
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

        if locref.noffs > 0:
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

    @staticmethod
    def build_decoded_ls(decode_result: LineLocation) -> LineString:
        tmp: LineString = geoutils.join_lines([line.geometry for line in decode_result.lines])
        pos_off = decode_result.p_off
        neg_off = decode_result.n_off
        if pos_off > 0 or neg_off > 0:
            ls_length: float = sum([line.length for line in decode_result.lines])
            if ls_length - pos_off - neg_off < 1.0:
                # The decoded line is shorter than the sum of the offsets
                # Adjusts the offsets such that the line is at least 1 meter long
                additional_length = max(int(pos_off + neg_off - ls_length ) / 2, 1)
                pos_off = max(pos_off - additional_length, 0)
                neg_off = max(neg_off - additional_length, 0)
            if pos_off > 0:
                _, front = split_line(tmp, pos_off)
                if front is None:
                    return LineString([tmp.coords[-1], tmp.coords[-1]])
            else:
                front = tmp
            if neg_off > 0:
                _, back = split_line(front.reverse(), neg_off)
                if back is None:
                    return LineString([front.coords[0], front.coords[0]])
                back = back.reverse()
            else:
                back = front
            return back
        else:
            return tmp

    def create_buffer_reader(
        self, loc_ref: LineLocationReference, buffered_ls: Polygon
    ) -> BufferReader:
        return BufferReader(
            buffer=buffered_ls,
            loc_ref=loc_ref,
            tomtom_map_reader=self.map_reader,
            lrp_radius=self.lrp_radius,
        )

    def match_binary(
        self, binstr: str
    ) -> Tuple[LineLocation, LineString, CandidateCollector] | MatchResult:
        locref: LineLocationReference = binary_decode(binstr)
        if not isinstance(locref, LineLocationReference):
            return MatchResult.UNSUPPORTED_LOCATION_REFERENCE_TYPE
        return self.match_location(locref)

    def match_location(
        self, locref: LineLocationReference
    ) -> Tuple[LineLocation, LineString, CandidateCollector] | MatchResult:
        observer = CandidateCollector()
        location = self.map_reader.match_location(locref, observer=observer)
        if location is None:
            return MatchResult.DECODING_FAILED
        if not isinstance(location, LineLocation):
            return MatchResult.UNSUPPORTED_LOCATION_TYPE
        decoded_ls = self.build_decoded_ls(location)
        return location, decoded_ls, observer

    def analyze(self, olr: str, ls: LineString) -> Tuple[str, AnalysisResult, float]:
        """Analyze a location reference against a map"""
        logging.debug("Beginning analysis of OpenLR %s", olr)
        if self.map_bounds and not self.map_bounds.covers(ls):
            return olr, AnalysisResult.OUTSIDE_MAP_BOUNDS, 0.0

        loc_ref = binary_decode(olr)
        if not isinstance(loc_ref, LineLocationReference):
            return olr, AnalysisResult.UNSUPPORTED_LOCATION_TYPE, 0.0

        match self.match_location(loc_ref):
            case (line_location, decoded_ls, observer):
                buffered_ls: Polygon = buffer_wgs84_geometry(
                    ls, Point(ls.coords[0]), self.buffer_radius
                )
                if buffered_ls.covers(decoded_ls):
                    return olr, AnalysisResult.OK, 1.0
                else:
                    percentage_within_buffer = (
                        intersection(buffered_ls, decoded_ls).length / decoded_ls.length
                    )
                    if line_location.p_off > 0 or line_location.n_off > 0:
                        return (
                            olr,
                            self.adjust_locref_and_match(
                                loc_ref,
                                line_location,
                                decoded_ls,
                                buffered_ls,
                                observer,
                            ),
                            percentage_within_buffer,
                        )
                    else:
                        return (
                            olr,
                            self.analyze_within_buffer(
                                loc_ref, line_location, buffered_ls, observer
                            ),
                            percentage_within_buffer,
                        )
            case MatchResult.DECODING_FAILED:
                buffered_ls: Polygon = buffer_wgs84_geometry(
                    ls, Point(ls.coords[0]), self.buffer_radius
                )
                buffer_map_reader = self.create_buffer_reader(loc_ref, buffered_ls)
                return (
                    olr,
                    self.determine_restricted_decoding_failure_cause(buffer_map_reader),
                    0.0,
                )
            case MatchResult.UNSUPPORTED_LOCATION_TYPE:
                return olr, AnalysisResult.UNSUPPORTED_LOCATION_TYPE, 0.0

    def adjust_locref_and_match(
        self,
        loc_ref: LineLocationReference,
        unrestricted_line_location: LineLocation,
        decoded_ls: LineString,
        buffered_ls: Polygon,
        observer: CandidateCollector,
    ) -> AnalysisResult:
        try:
            adj_loc_ref = self.adjust_locref(loc_ref, decoded_ls)
        except GeodError as ge:
            return AnalysisResult.INVALID_GEOMETRY
        match self.match_location(adj_loc_ref):
            case (adj_loc, decoded_ls, adj_observer):
                if buffered_ls.covers(decoded_ls):
                    return self.compare_locations(
                        unrestricted_line_location,
                        observer,
                        adj_loc,
                        adj_observer,
                    )
                else:
                    return self.analyze_within_buffer(
                        adj_loc_ref, adj_loc, buffered_ls, adj_observer
                    )
            case MatchResult.DECODING_FAILED:
                buffer_map_reader = self.create_buffer_reader(loc_ref, buffered_ls)
                return self.determine_restricted_decoding_failure_cause(
                    buffer_map_reader
                )
            case MatchResult.UNSUPPORTED_LOCATION_TYPE:
                return AnalysisResult.UNSUPPORTED_LOCATION_TYPE

    def analyze_within_buffer(
        self,
        loc_ref: LineLocationReference,
        loc: LineLocation,
        buffered_ls: Polygon,
        observer: CandidateCollector,
    ) -> AnalysisResult:
        buffer_map_reader = self.create_buffer_reader(loc_ref, buffered_ls)
        buffer_observer = CandidateCollector()
        buffer_loc = buffer_map_reader.match(
            config=StrictConfig, observer=buffer_observer
        )
        if buffer_loc:
            return self.compare_locations(
                loc,
                observer,
                buffer_loc,
                buffer_observer,
            )
        else:
            return self.determine_restricted_decoding_failure_cause(buffer_map_reader)

    @staticmethod
    def determine_restricted_decoding_failure_cause(
        buffer_map_reader: BufferReader,
    ) -> AnalysisResult:
        # We're here because we couldn't find a path in the restricted target map

        if not buffer_map_reader.match(config=AnyPath):
            return AnalysisResult.MISSING_OR_MISCONFIGURED_ROAD
        if buffer_map_reader.match(config=IgnoreFRC):
            return AnalysisResult.FRC_MISMATCH
        if buffer_map_reader.match(config=IgnoreFOW):
            return AnalysisResult.FOW_MISMATCH
        if buffer_map_reader.match(config=IgnorePathLength):
            return AnalysisResult.PATH_LENGTH_MISMATCH
        if buffer_map_reader.match(config=IgnoreBearing):
            return AnalysisResult.BEARING_MISMATCH
        return AnalysisResult.MULTIPLE_ATTRIBUTE_MISMATCHES

    def diagnose_score(
        self,
        lrp: LocationReferencePoint,
        outside: Candidate,
        inside: Candidate,
        is_last: bool,
    ) -> AnalysisResult:
        # assert outside.score >= inside.score
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
            return AnalysisResult.BETTER_FRC_FOUND
        if in_score_collector.bear_reject:
            return AnalysisResult.BETTER_BEARING_FOUND
        if in_score_collector.score_reject:
            return AnalysisResult.BETTER_SCORE_FOUND

        components = [0.0, 0.0, 0.0, 0.0]
        components[0] = self.map_reader.config.geo_weight * (
            out_score_collector.geo_score - in_score_collector.geo_score
        )
        components[1] = self.map_reader.config.bear_weight * (
            out_score_collector.bear_score - in_score_collector.bear_score
        )
        components[2] = self.map_reader.config.frc_weight * (
            out_score_collector.frc_score - in_score_collector.frc_score
        )
        components[3] = self.map_reader.config.fow_weight * (
            out_score_collector.fow_score - in_score_collector.fow_score
        )

        match components.index(max(components)):
            case 0:
                return AnalysisResult.BETTER_GEOLOCATION_FOUND
            case 1:
                return AnalysisResult.BETTER_BEARING_FOUND
            case 2:
                return AnalysisResult.BETTER_FRC_FOUND
            case 3:
                return AnalysisResult.BETTER_FOW_FOUND

    def compare_locations(
        self,
        outside_loc: LineLocation,
        outside_obs: CandidateCollector,
        inside_loc: LineLocation,
        inside_obs: CandidateCollector,
    ) -> AnalysisResult:
        assert len(outside_obs.candidates) == len(inside_obs.candidates)
        outside_pairs = [
            outside_obs.candidates[i] for i in sorted(outside_obs.candidates)
        ]
        inside_pairs = [inside_obs.candidates[i] for i in sorted(inside_obs.candidates)]

        if (outside_pairs[0][1].line.line_id != inside_pairs[0][1].line.line_id) and (
            outside_pairs[0][1].line.end_node.node_id
            != inside_pairs[0][1].line.start_node.node_id
        ):
            return self.diagnose_score(
                lrp=outside_pairs[0][0],
                outside=outside_pairs[0][1],
                inside=inside_pairs[0][1],
                is_last=False,
            )

        for outside, inside in zip(
            outside_pairs[1:-1],
            inside_pairs[1:-1],
        ):
            assert outside[0] == inside[0]
            if outside[1].line.line_id != inside[1].line.line_id:
                return self.diagnose_score(
                    lrp=outside[0], outside=outside[1], inside=inside[1], is_last=False
                )

        if (outside_pairs[-1][1].line.line_id != inside_pairs[-1][1].line.line_id) and (
            outside_pairs[-1][1].line.start_node.node_id
            != inside_pairs[-1][1].line.end_node.node_id
        ):
            return self.diagnose_score(
                lrp=outside_pairs[-1][0],
                outside=outside_pairs[-1][1],
                inside=inside_pairs[-1][1],
                is_last=True,
            )
        return AnalysisResult.ALTERNATE_SHORTEST_PATH
