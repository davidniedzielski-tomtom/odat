from enum import Enum

class MatchResult(Enum):
    OK = 0,
    UNKNOWN_LOCATION_REFERENCE_TYPE = 1,
    INVALID_LOCATION_REFERENCE = 2,
    DECODING_FAILED = 3,

