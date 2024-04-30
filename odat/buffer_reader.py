"""
Implements the OpenLR python decoder protocol for a SQLite/Spatialite
DB containing the schema used by the TomTom OpenLR WebTool.

That is, lines (roads) can be two-way, as opposed to one-way only.  This
module dynamically duplicates and/or reverses roads so that the decoder
sees only one-way roads. It uses the "direction" column in the lines table
to determine whether this is necessary.

Dependencies:
    - openlr
    - openlr_dereferencer
    - pyproj
    - param

"""

from __future__ import annotations

import logging
from contextlib import closing
from math import sqrt
from typing import Iterable, Optional, cast, Dict, Set

from geoutils import distance
from openlr import Coordinates, FOW, FRC
from openlr.locations import LineLocationReference
from openlr_dereferencer import decode, Config, DecoderObserver
from openlr_dereferencer.decoding import MapObjects, DEFAULT_CONFIG
from openlr_dereferencer.maps import MapReader
from shapely import wkb
from shapely.geometry import LineString, Polygon
from webtool.map_databases.tomtom_sqlite import TomTomMapReaderSQLite

from odat.buffer_line import Line
from odat.buffer_node import Node

SQRT_2 = sqrt(2)


class WebToolMapException(Exception):
    pass


# @MapReader.register
class BufferReader(MapReader):

    def __init__(
        self,
        loc_ref: LineLocationReference,
        buffer: Polygon,
        tomtom_map_reader: TomTomMapReaderSQLite,
        lrp_radius: int = 20,
        config: Config = DEFAULT_CONFIG,
    ):

        self.loc_ref = loc_ref
        self.tomtom_map_reader = tomtom_map_reader
        self.connection = tomtom_map_reader.connection
        self.geo_tool = tomtom_map_reader.geo_tool
        self.lines_table = tomtom_map_reader.lines_table
        self.nodes_table = tomtom_map_reader.nodes_table
        self.lrp_radius = lrp_radius
        self.config = config
        self.buffer = buffer
        self.nodes: Dict[str, Node] = {}
        self.lines: Dict[str, Line] = {}
        self.all_lines: Set[Line] = set()
        self.incoming_lines: Dict[str, Set[Line]] = {}
        self.outgoing_lines: Dict[str, Set[Line]] = {}
        self.candidates = {}
        self.init_objects()

    def init_objects(self):
        self.find_all_candidate_lines()
        for line in self.all_lines:
            self.nodes[line.from_int] = self.nodes.get(
                line.from_int,
                Node(
                    self,
                    line.from_int,
                    line.geometry.coords[0][0],
                    line.geometry.coords[0][1],
                    self.buffer,
                ),
            )
            self.nodes[line.to_int] = self.nodes.get(
                line.to_int,
                Node(
                    self,
                    line.to_int,
                    line.geometry.coords[-1][0],
                    line.geometry.coords[-1][1],
                    self.buffer,
                ),
            )
            self.update_node_outgoing(line)
            self.update_node_incoming(line)

    def find_all_candidate_lines(self) -> None:
        min_lon, min_lat, max_lon, max_lat = self.buffer.bounds
        with closing(self.connection.cursor()) as cursor:
            sql = f"""
                select
                    r.id, r.fow, r.frc, r.direction, r.start_id, r.end_id, r.length, st_asbinary(r.geom)
                from
                    {self.lines_table} r
                where
                    rowid in ( SELECT ROWID FROM SpatialIndex WHERE f_table_name="{self.lines_table}" AND search_frame=buildmbr({min_lon}, {min_lat}, {max_lon}, {max_lat}))
                and
                    st_intersects(st_GeomFromText('{self.buffer.wkt}'), r.geom)
            """
            cursor.execute(sql)
            self.create_lines(cursor.fetchall())

    def create_lines(self, rows) -> None:
        for line_id, fow, frc, flowdir, start, end, length, geom in rows:
            ls = LineString(wkb.loads(geom, hex=False))
            line = Line(
                map_reader=self,
                line_id=line_id,
                from_int=str(start),
                to_int=str(end),
                fow=FOW(fow),
                frc=FRC(frc),
                length=length,
                geometry=ls,
                buffer=self.buffer,
            )
            self.lines[line.id] = line
            self.all_lines.add(line)
            if flowdir == 1:
                rev_line = Line(
                    map_reader=self,
                    line_id="-" + line_id,
                    from_int=str(end),
                    to_int=str(start),
                    fow=FOW(fow),
                    frc=FRC(frc),
                    length=length,
                    geometry=ls.reverse(),
                    buffer=self.buffer,
                )
                self.lines[rev_line.id] = rev_line
                self.all_lines.add(rev_line)

    def update_node_outgoing(self, line: Line):
        if line.start_node.node_id in self.outgoing_lines:
            self.outgoing_lines[str(line.start_node.node_id)].add(line)
        else:
            self.outgoing_lines[str(line.start_node.node_id)] = {line}

    def update_node_incoming(self, line: Line):
        if line.end_node.node_id in self.incoming_lines:
            self.incoming_lines[str(line.end_node.node_id)].add(line)
        else:
            self.incoming_lines[str(line.end_node.node_id)] = {line}

    def match(
        self,
        config: Optional[Config] = None,
        observer: Optional[DecoderObserver] = None,
    ) -> Optional[MapObjects]:
        """
        Decode an OpenLR binary string

        Arguments:
            observer: Optional DecoderObser instance to monitor decoding
            config:Optional[Config]
                configuration object which overrides instance level config
                Default: None

        Returns:
            A registered subtype of MapObjects( currently Coordinates, LineLocation,
            PointAlongLine, or PoiWithAccessPoint)

        Raises:
            LRDecodeError:
                Raised if the decoding process was not successful.
        """
        if config is None:
            config = self.config
        try:
            return cast(
                MapObjects,
                decode(
                    reference=self.loc_ref,
                    reader=cast(MapReader, self),
                    observer=observer,
                    config=cast(Config, config),
                    geo_tool=self.geo_tool,
                ),
            )
        except Exception as e:
            logging.info(f"Error during initial decode of {self.loc_ref}: {e}")
            return None

    def get_line(self, line_id: str) -> Line:
        # Just verify that this line ID exists.
        line = self.lines.get(line_id)
        if line is not None:
            return line
        raise WebToolMapException(
            f"Line {line_id} should have been in the cache but was not found"
        )

    def get_lines(self) -> Iterable[Line]:
        logging.warning("Unimplemented function get_lines() invoked in buffer_reader")
        return []

    def get_linecount(self) -> int:
        return len(self.lines)

    def get_node(self, node_id: str) -> Node:
        n = self.nodes.get(node_id)
        if n is not None:
            return n
        raise WebToolMapException(
            f"Line {node_id} should have been in the cache but was not found"
        )

    def get_nodes(self) -> Iterable[Node]:
        logging.warning("Unimplemented function get_lines() invoked in buffer_reader")
        return []

    def get_nodecount(self) -> int:
        return len(self.nodes)

    def find_nodes_close_to(self, coord: Coordinates, dist: float) -> Iterable[Node]:
        return [
            node
            for node in self.nodes.values()
            if node.contained_in_buffer and distance(coord, node.coordinates) < dist
        ]

    def find_lines_close_to(self, coord: Coordinates, dist: float) -> Iterable[Line]:
        # allow lines that are not contained in the buffer if they are being considered for the first or last lrp
        if (
            self.loc_ref.points[0][0] == coord[0]
            and self.loc_ref.points[0][1] == coord[1]
        ) or (
            self.loc_ref.points[-1][0] == coord[0]
            and self.loc_ref.points[-1][1] == coord[1]
        ):
            candidates = [ line for line in self.lines.values() if line.distance_to(coord) < dist ]
            for line in candidates:
                if not line.contained_in_buffer:
                    line.entry_or_exit = True
            return candidates
        else:
            return [
                line
                for line in self.lines.values()
                if line.contained_in_buffer and line.distance_to(coord) < dist
            ]
