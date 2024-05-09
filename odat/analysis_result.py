from enum import Enum

"""
    This module defines the AnalysisResult enum, which is used to categorize the results of the analysis of OpenLR
    codes.  The results are used to generate statistics on the quality of the OpenLR codes, as well as to identify
    potential issues with the OpenLR source or target maps.  
    
    The term "buffer" is used to refer to the buffer polygon around the encoded linestring geometry.  The width of
    this buffer defaults to 20 meters, but can be adjusted by the user.  The buffer is used to determine whether the    
    decoded geometry is spatially similar to the encoded geometry in addition to being acceptable from an OpenLR 
    perspective.
    
    ODAT analysis starts with taking an OpenLR code as well as a LineString WKT representing the location that the 
    encoder was asked to encode when it produced that OpenLR.  ODAT builds a polygonal buffer of a user-specified 
    diameter around this LineString.  Next, the decoder attempts to decode the OpenLR against the target map, and 
    if it is successful, determines whether the decoded geometry is completely covered by the buffer. If so, the 
    result is "OK", because the decoded and encoded locations are both spatially similar and acceptable from an 
    OpenLR standpoint.  If not, or it the decoding failed, ODAT attempts to determine the cause of the discrepancy.  
    For example, if the decoding failed completely, it checks to see if there is a "viable" path between the start 
    and end LRPs that lies within the buffer.  If so, then a series of decodings are attempted to determine 
    why that path was not selected by the decoder.  Note that a "viable" path is a path that is continuous and 
    connects the start and end LRPs, is composed of roads that are fully within the buffer, and obeys one-way 
    directions. 
    
    On the other hand, if the decoding was successful but the decoded geometry was not completely within the buffer,
    ODAT checks the placement of the LRPs to verify that they are all placed within the buffer.  If not, then ODAT
    determines why the external LRP placements were preferable to internal ones.
    
    In all cases, the results of the analysis are described and categorized by the AnalysisResult enum.
    
"""


class AnalysisResult(Enum):
    """
        Decoding was successful, and the decoded line_string was completely within the buffer
    """
    OK = 0,

    """ 
        Decoding was unsuccessful, and no viable path could be found within the buffer.  This is probably
        due to missing or misconfigured roads in the target map, but could also occur if the feeds include
        OpenLRs that are beyond the extent of the SQLite DB map
    """
    MISSING_OR_MISCONFIGURED_ROAD = 1,

    """
        Decoding was successful, but the decoded line_string was not completely within the buffer.  Furthermore,
        the LRPs were all placed within the buffer.  The most logical explanation is that one or more roads are
        present in the target map (not in the source map) which form a shorter path than the one which was encoded.
        Alternatively, those roads exist in the source map but have an FRC too low to be considered by the encoder.
    """
    ALTERNATE_SHORTEST_PATH = 2,

    """
        Decoding either failed, or else the decoded line_string was not completely within the buffer.  However, a viable
        path was found within the buffer that the decoder did not consider.  Furthermore, the decoder *did* select that 
        path in the buffer once the FRC/LFRC restrictions were ignored.  This means that one or more roads within the
        buffer in the target map has an FRC that is too low to be considered by the decoder, whereas the same roads 
        in the source map have acceptable FRCs.
    """
    FRC_MISMATCH = 3,

    """
        Decoding either failed, or else the decoded line_string was not completely within the buffer.  However, a viable
        path was found within the buffer that the decoder did not consider.  Furthermore, the decoder *did* select that 
        path in the buffer once the FOW restrictions were ignored.  This means that one or more roads within the
        buffer in the target map has an FOW that is not compatible with the FOW in one or more of the LRPs.
    """
    FOW_MISMATCH = 4,

    """
        Decoding either failed, or else the decoded line_string was not completely within the buffer.  However, a viable
        path was found within the buffer that the decoder did not consider.  Furthermore, the decoder *did* select that 
        path in the buffer once the bearing restrictions were ignored.  This means that one or more roads within the
        buffer in the target map has a bearing that is not compatible with the bearing in one or more of the LRPs.
    """
    BEARING_MISMATCH = 5,

    """
        Decoding either failed, or else the decoded line_string was not completely within the buffer.  However, a viable
        path was found within the buffer that the decoder did not consider.  Furthermore, the decoder *did* select that 
        path in the buffer once the path length restrictions were ignored.  This likely means that either the encoded
        path was not the one intended, or else roads are missing in the target map that were necessary to form an
        acceptably short shortest path.
    """
    PATH_LENGTH_MISMATCH = 6,

    """
        At present, only line locations are supported by ODAT
    """
    UNSUPPORTED_LOCATION_TYPE = 7,

    """
        Decoding either failed, or else the decoded line_string was not completely within the buffer.  However, a viable
        path was found within the buffer that the decoder did not consider.  Furthermore, individually ignoring OpenLR
        attributes like FRC, FOW, bearing, and path length failed to convince the decoder to select that viable buffer
        path.  This means that a combination of attributes such as bearing *and* FRC are incompatible with those in the
        LRPs.
    """
    MULTIPLE_ATTRIBUTE_MISMATCHES = 8,

    """
        An exception was encountered during the analysis.  Refer to log messages for the cause.
    """
    UNKNOWN_ERROR = 9,

    """
        The encoded line string lies outside of the SQLite DB map extent.  This is not necessarily an error, but
        a large number of these errors could mean that the OpenLR source is from a different geographical region 
        than the one represented by the SQLite DB map.  
    """
    OUTSIDE_MAP_BOUNDS = 10,

    """
        The analyzer was given an OpenLR code that it had already analyzed.  This is probably not an error, especially
        if the input is derived from the incident feed.  These duplicates are ignored and are not counted when 
        computing the final statistics.
    """
    DUPLICATE_OPENLR_CODE = 11,

    """
        Decoding was successful, but the decoded geometry was not completely within the buffer.  Furthermore, at least
        one LRP was placed on a line outside of the buffer, and this line's geolocation rating was the greatest factor
        in its being selected over the corresponding candidate within the buffer.
    """
    BETTER_GEOLOCATION_FOUND = 12,

    """
        Decoding was successful, but the decoded geometry was not completely within the buffer.  Furthermore, at least
        one LRP was placed on a line outside of the buffer, and this line's bearing rating was the greatest factor
        in its being selected over the corresponding candidate within the buffer.
    """
    BETTER_BEARING_FOUND = 13,

    """
        Decoding was successful, but the decoded geometry was not completely within the buffer.  Furthermore, at least
        one LRP was placed on a line outside of the buffer, and this line's FRC rating was the greatest factor
        in its being selected over the corresponding candidate within the buffer.
    """
    BETTER_FRC_FOUND = 14,

    """
        Decoding was successful, but the decoded geometry was not completely within the buffer.  Furthermore, at least
        one LRP was placed on a line outside of the buffer, and this line's FOW rating was the greatest factor
        in its being selected over the corresponding candidate within the buffer.
    """
    BETTER_FOW_FOUND = 15,

    """
        Decoding was successful, but the decoded geometry was not completely within the buffer.  Furthermore, at least
        one LRP was placed on a line outside of the buffer, and more than one LRP attribute (FRC, FOW, bearing, 
        geolocation) was responsible for its being preferred over the corresponding candidate within the buffer. 
    """
    BETTER_SCORE_FOUND = 16,

    """
        During the conversion of the OpenLR code to one representing a path completely within the buffer, PYPROJ
        threw an exception.  This is likely caused by the positive and negative offsets reducing the location to
        zero length.  Turn on debugging for additional diagnostics.
    """
    INVALID_GEOMETRY = 17,
