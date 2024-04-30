from typing import Optional, Iterable

from openlr import Coordinates
from shapely import Polygon, Point
from openlr_dereferencer.maps import Node as AbstractNode

from odat.buffer_line import Line

from itertools import chain

def are_peers(candidate: Line, source: Optional[Line]) -> bool:
    """
    Returns True if candidate and source are peer lines, i.e. they are
    the same road, but in opposite directions.  This is determined
    by the line_id of the lines.

    Arguments:
        candidate:Line
            first line
        source:Optional[Line]
            second line

    Returns:
        bool
            True if candidate and source are peer lines, False otherwise
    """
    if source is None:
        return False
    else:
        return (
            candidate.line_id == "-" + source.line_id
            or source.line_id == "-" + candidate.line_id
        )


class Node(AbstractNode):

    def __init__(
        self,
        map_reader: "BufferReader",
        node_id: str,
        lon: float,
        lat: float,
        buffer: Polygon,
    ):
        self.lon = lon
        self.lat = lat
        self.id = node_id
        self.map_reader = map_reader
        self.incoming_lines_cache = []
        self.outgoing_lines_cache = []
        self.contained_in_buffer = buffer.contains(Point(lon, lat))

    @property
    def node_id(self):
        return self.id

    @property
    def coordinates(self) -> Coordinates:
        return Coordinates(lon=self.lon, lat=self.lat)

    def outgoing_lines(self, source: Optional[Line] = None) -> Iterable[Line]:
        if self.id in self.map_reader.outgoing_lines:
            return [
                line
                for line in self.map_reader.outgoing_lines[self.id]
                if (line.contained_in_buffer or line.entry_or_exit) and not are_peers(line, source)
            ]
        else:
            return []

    def incoming_lines(self, source: Optional[Line] = None) -> Iterable[Line]:
        if self.id in self.map_reader.incoming_lines:
            return [
                line
                for line in self.map_reader.incoming_lines[self.id]
                if (line.contained_in_buffer or line.entry_or_exit) and not are_peers(line, source)
            ]
        else:
            return []

    def connected_lines(self) -> Iterable[Line]:
        return chain(self.incoming_lines(), self.outgoing_lines())
