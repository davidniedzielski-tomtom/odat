# OpenLR Decoding Analysis Tool
This tool analyzes the decoding on a target map  of an OpenLR code that was originally decoded on a source map.
It not only checks if the decoding was _successful_ (i.e. was able to match a location on the target map), but also
the _accuracy_ of the decoding.  A decoding is considered accurate if the decoded location is completely contained in
a buffer surrounding the encoded location.  The buffer size is configurable.

If the decoding was not successful or was deemed inaccurate, the tool attempts to determine why the error occurs.  It
does so by attempting a series of additional decodings, each of which is a slight variation of the original decoding.
Each subsequent decoding "masks out" an OpenLR attribute until the decoding is successful or all attributes have been
masked out.  The tool then reports which attribute(s) caused the error.

# Input
The tool requires a JSON-encoded source file containing at a minimum a set of OpenLR codes as well as a LineString
WKT describing the location of the OpenLR code(s) on the source map.  The tool also requires a SQLite target map in 
the canonical TomTom schema.  A Spatialite extenion shared object is also required.These requirements are the same 
as the map similarity tool. The schema is described below.

Links table:

```sql
    CREATE TABLE links (
    id TEXT PRIMARY KEY,
    uuid TEXT,
    start_id TEXT NOT NULL,
    end_id TEXT NOT NULL,
    direction INTEGER NOT NULL,
    frc INTEGER NOT NULL,
    fow INTEGER NOT NULL,
    length REAL NOT NULL
    , "geom" LINESTRING NOT NULL DEFAULT '', minx REAL NOT NULL, maxx REAL NOT NULL, miny REAL NOT NULL, maxy REAL NOT NULL);
```

Junctions table:

```sql
    CREATE TABLE junctions (
    id TEXT PRIMARY KEY
    , "geom" POINT NOT NULL DEFAULT '');
```

# Output
For each OpenLR passed to the tool, it will return a ENUM describing the results of the analysis. The ENUM is defined
as follows:
```python
class AnalysisResult(Enum):
    OK = 0,
    MISSING_OR_MISCONFIGURED_ROAD = 1,
    ALTERNATE_SHORTEST_PATH = 2,
    FRC_MISMATCH = 3,
    FOW_MISMATCH = 4,
    BEARING_MISMATCH = 5,
    PATH_LENGTH_MISMATCH = 6,
    UNSUPPORTED_LOCATION_TYPE = 7,
    DECODING_ERROR = 8,
    INCORRECT_FIRST_OR_LAST_LRP_PLACEMENT = 9,
    UNKNOWN_ERROR = 10,
    OUTSIDE_MAP_BOUNDS = 11
```


