import geoutils
from openlr import FRC, FOW
from openlr_dereferencer.maps import Line as AbstractLine
from pyproj import Geod
from shapely import LineString, Polygon, Point

GEOD = Geod(ellps="WGS84")


class Line(AbstractLine):

    def __init__(
        self,
        map_reader: "BufferReader",
        line_id: str,
        fow: FOW,
        frc: FRC,
        length: float,
        from_int: str,
        to_int: str,
        geometry: LineString,
        buffer: Polygon,
    ):
        self.id: str = line_id
        self.map_reader: "BufferReader" = map_reader
        self._fow: FOW = fow
        self._frc: FRC = frc
        self._length: float = length
        self.from_int: str = from_int
        self.to_int: str = to_int
        self._geometry: LineString = geometry
        self.contained_in_buffer = buffer.contains(self._geometry)
        self.entry_or_exit = False

    def __repr__(self):
        return f"Line with id={self.line_id} of length {self.length}"

    @property
    def line_id(self) -> str:
        """Returns the line id"""
        return self.id

    @property
    def start_node(self) -> "Node":
        return self.map_reader.nodes[self.from_int]

    @property
    def end_node(self) -> "Node":
        return self.map_reader.nodes[self.to_int]

    @property
    def length(self):
        return self._length

    @property
    def frc(self):
        return self._frc

    @property
    def fow(self):
        return self._fow

    @property
    def geometry(self):
        return self._geometry

    def distance_to(self, coord) -> float:
        """Returns the distance of this line to `coord` in meters"""
        # if (self.geometry.coords[0] == coord or self.geometry.coords[-1] == coord) or (
        #     self.geometry.coords[0] == self.geometry.coords[-1]
        # ):
        #     return 0.0
        return geoutils.distance_between(self.geometry, Point(coord.lon, coord.lat))
