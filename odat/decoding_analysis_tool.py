import logging
from typing import Tuple

import geoutils
from geoutils import buffer_wgs84_geometry, split_line, GeoCoordinates
from openlr import LineLocationReference, LocationReferencePoint, binary_decode
from openlr_dereferencer.decoding import MapObjects
from openlr_dereferencer.decoding.line_decoding import LineLocation
from shapely import LineString, Point, Polygon, intersection
from webtool.decoder_configs import (
    StrictConfig,
    AnyPath,
    IgnoreFRC,
    IgnoreFOW,
    IgnorePathLength,
    IgnoreBearing,
)
from webtool.map_databases.tomtom_sqlite import TomTomMapReaderSQLite

from .analysis_result import AnalysisResult
from .buffer_reader import BufferReader


class DecodingAnalysisTool:

    def __init__(
        self,
        map_reader: TomTomMapReaderSQLite,
        buffer_radius: int = 20,
        lrp_radius: int = 20,
    ):
        self.map_reader = map_reader
        self.buffer_radius = buffer_radius
        self.lrp_radius = lrp_radius
        self.logger = logging.getLogger(__name__)  # self.logger.setLevel(logging.DEBUG)
        self.map_bounds: Polygon = self.map_reader.get_map_bounds()

    @staticmethod
    def build_decoded_ls(decode_result: LineLocation) -> LineString:
        tmp = geoutils.join_lines([line.geometry for line in decode_result.lines])
        if decode_result.p_off > 0:
            _, front = split_line(tmp, decode_result.p_off)
            if front is None:
                return LineString([tmp.coords[-1], tmp.coords[-1]])
        else:
            front = tmp
        if decode_result.n_off > 0:
            _, back = split_line(front.reverse(), decode_result.n_off)
            if back is None:
                return LineString([front.coords[0], front.coords[0]])
            back = back.reverse()
        else:
            back = front
        return back

    def analyze(self, olr: str, ls: LineString) -> Tuple[AnalysisResult, float]:
        """Analyze a location reference against a map"""
        if not self.map_bounds.contains(ls):
            return AnalysisResult.OUTSIDE_MAP_BOUNDS, 0.0

        decode_result: MapObjects = self.map_reader.match(olr)
        if decode_result is not None:
            if isinstance(decode_result, LineLocation):
                buffered_ls: Polygon = buffer_wgs84_geometry(
                    ls, Point(ls.coords[0]), self.buffer_radius
                )
                decoded_ls: LineString = self.build_decoded_ls(decode_result)
                if buffered_ls.contains(decoded_ls):
                    return AnalysisResult.OK, 1.0
                else:
                    # build a buffer around the source linestring
                    percentage_within_buffer = (
                        intersection(buffered_ls, decoded_ls).length / decoded_ls.length
                    )
                    loc_ref = self.adjust_locref(olr, ls)
                    buffer_map_reader = BufferReader(
                        buffer=buffered_ls,
                        loc_ref=loc_ref,
                        tomtom_map_reader=self.map_reader,
                        lrp_radius=self.buffer_radius,
                    )
                    return (
                        self.analyze_within_buffer(
                            buffer_map_reader, decoded_ls, olr, buffered_ls
                        ),
                        percentage_within_buffer,
                    )
            else:
                return AnalysisResult.UNSUPPORTED_LOCATION_TYPE, 0.0
        else:
            buffered_ls: Polygon = buffer_wgs84_geometry(
                ls, Point(ls.coords[0]), self.buffer_radius
            )
            return (
                self.determine_unrestricted_decoding_failure_cause(olr, buffered_ls),
                0.0,
            )

    @staticmethod
    def adjust_locref(olr: str, ls: LineString) -> LineLocationReference:
        """
        Adjust the location reference so that the entire location reference is within the buffer

        Args:
            olr: OpenLR string being analyzed
            ls: LineString resulting from source map decoding

        Returns: possibly modified location reference

        """
        locref: LineLocationReference = binary_decode(olr)
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

    def analyze_within_buffer(
        self,
        buffer_map_reader: BufferReader,
        decoded_ls: LineString,
        olr: str,
        buffered_ls: Polygon,
    ) -> AnalysisResult:
        # We were able to decode in the unrestricted map, but the location didn't fit within the
        # buffer.  See if a valid path even exists in the restricted buffer and if so, compare
        # the lengths of the two paths.
        res = buffer_map_reader.match(StrictConfig)
        if res:
            ls_within_buffer = self.build_decoded_ls(res)
            if geoutils.line_string_length(
                ls_within_buffer
            ) > geoutils.line_string_length(decoded_ls):
                return AnalysisResult.ALTERNATE_SHORTEST_PATH
            else:
                return self.determine_unrestricted_decoding_failure_cause(
                    olr, buffered_ls
                )
        else:
            return self.determine_restricted_decoding_failure_cause(buffer_map_reader)

    @staticmethod
    def determine_restricted_decoding_failure_cause(
            buffer_map_reader: BufferReader
    ) -> AnalysisResult:
        # We're here because we couldn't find a path in the restricted target map, but
        #

        if not buffer_map_reader.match(AnyPath):
            return AnalysisResult.MISSING_OR_MISCONFIGURED_ROAD
        if buffer_map_reader.match(IgnoreFRC):
            return AnalysisResult.FRC_MISMATCH
        if buffer_map_reader.match(IgnoreFOW):
            return AnalysisResult.FOW_MISMATCH
        if buffer_map_reader.match(IgnorePathLength):
            return AnalysisResult.PATH_LENGTH_MISMATCH
        if buffer_map_reader.match(IgnoreBearing):
            return AnalysisResult.BEARING_MISMATCH
        return AnalysisResult.INCORRECT_FIRST_OR_LAST_LRP_PLACEMENT

    def determine_unrestricted_decoding_failure_cause(
        self, olr: str, buffered_ls: Polygon
    ):
        # We're here because the location we decoded against the unrestricted target map
        # does not fit within the source map decoding's buffer.  However, we were able
        # to find a location completely in the restricted target map that is shorter than the unrestricted
        # location.  So why did our unrestricted decoding not take the path within the buffer?
        # It can't be an LFRC issue, because the path we found in the restricted map met those
        # requirements.  The logical assumption is that the LRPs were snapped to different locations
        # in the source map than they were in the unrestricted target map.

        if not self.map_reader.match(olr, config=AnyPath):
            return AnalysisResult.MISSING_OR_MISCONFIGURED_ROAD

        res = self.map_reader.match(olr, config=IgnoreFRC)
        if res is not None and buffered_ls.contains(self.build_decoded_ls(res)):
            return AnalysisResult.FRC_MISMATCH

        res = self.map_reader.match(olr, config=IgnoreFOW)
        if res is not None and buffered_ls.contains(self.build_decoded_ls(res)):
            return AnalysisResult.FOW_MISMATCH

        res = self.map_reader.match(olr, config=IgnorePathLength)
        if res is not None and buffered_ls.contains(self.build_decoded_ls(res)):
            return AnalysisResult.PATH_LENGTH_MISMATCH

        res = self.map_reader.match(olr, config=IgnoreBearing)
        if res is not None and buffered_ls.contains(self.build_decoded_ls(res)):
            return AnalysisResult.BEARING_MISMATCH

        return AnalysisResult.INCORRECT_FIRST_OR_LAST_LRP_PLACEMENT

    def compare_lrp_with_paths(self):
        pass
