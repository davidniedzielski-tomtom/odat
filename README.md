# OpenLR Decoding Analysis Tool (ODAT)

The ODAT tool attempts to analyze how well a set of OpenLR codes encoded on a source map decodes on a target map. It
accepts as input a JSON file containing a set of OpenLR codes as well as the LineString WKT that the OpenLR is 
*supposed* to represent (on the source map), and a SQLite database in the canonical TomTom schema representing some 
target map.

For each OpenLR/LineString in the input set, ODAT builds a polygonal buffer of a user-specified 
diameter around the intended LineString.  Next, the decoder attempts to decode the OpenLR against the target map, and 
if it is successful, determines whether the decoded geometry is completely contained within the buffer. If so, the 
result is "OK", because the decoded and encoded locations are both spatially similar and acceptable from an 
OpenLR standpoint.  If not, or it the decoding failed, ODAT attempts to determine the cause of the failure.  

For example, if the decoding failed completely, it checks to see if there is a "viable" path between the start 
and end LRPs that lies within the buffer.  A "viable" path is a path that is continuous and 
connects the start and end LRPs, is composed of roads that are fully within the buffer, and obeys one-way 
directions. If such a path exists, then a series of decodings are attempted to determine why that path was not 
selected by the decoder.  On the other hand, if the decoding was successful but the decoded geometry was not completely 
within the buffer, ODAT checks the placement of the LRPs to verify that they are all placed within the buffer.  If 
any are placed on lines outside the buffer, then ODAT determines why the external LRP placements were preferable to 
internal ones. 

Alternatively, if the decoding failed but the location was not completely outside the buffer, ODAT begins an analysis
of the LRP-to-line placement.  If LRPs were placed on lines not within the buffer, ODAT uses the observer pattern of
the Python reference implementation to ascertain why the LRPs were placed on those lines instead of the lines within
the buffer.

In all cases, the results of the analysis are described and categorized by the AnalysisResult enum.

# Input
The tool requires a JSON-encoded source file containing at a minimum a set of OpenLR codes as well as a LineString
WKT describing the location of the OpenLR code(s) on the source map.  The tool also requires a SQLite target map in 
the canonical TomTom schema.  A Spatialite extension shared object is also required. These requirements are the same 
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
in `odat/analysis_result.py`.

