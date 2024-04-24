from typing import Dict

from openlr import FRC

from openlr_dereferencer.decoding import Config

#: When comparing an LRP FOW with a candidate's FOW, this matrix defines
#: how well the candidate's FOW fits as replacement for the expected value.
#: The usage is `fow_standin_score[lrp's fow][candidate's fow]`.
#: It returns the score.
STRICT_FOW_STAND_IN_SCORE = [
    [0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.1],  # 0 = Undefined FOW
    [0.50, 1.00, 0.75, 0.25, 0.00, 0.00, 0.00, 0.1],  # 1 = Motorway
    [0.50, 0.75, 1.00, 0.75, 0.50, 0.00, 0.00, 0.1],  # 2 = Multiple carriage way
    [0.50, 0.00, 0.75, 1.00, 0.50, 0.50, 0.00, 0.1],  # 3 = Single carriage way
    [0.50, 0.00, 0.00, 0.50, 1.00, 0.50, 0.00, 0.1],  # 4 = Roundabout
    [0.50, 0.00, 0.00, 0.50, 0.50, 1.00, 0.00, 0.1],  # 5 = Traffic square
    [0.50, 0.50, 0.40, 0.30, 0.00, 0.00, 1.00, 0.1],  # 6 = Sliproad
    [0.50, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 1.0],  # 7 = Other FOW
]

RELAXED_FOW_STAND_IN_SCORE = [
    [1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00],  # 0 = Undefined FOW
    [1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00],  # 1 = Motorway
    [1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00],  # 2 = Multiple carriage way
    [1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00],  # 3 = Single carriage way
    [1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00],  # 4 = Roundabout
    [1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00],  # 5 = Traffic square
    [1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00],  # 6 = Sliproad
    [1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00],  # 7 = Other FOW
]

# Decoding is first attempted using strict decoding parameters,
# and then retried with more lenient ones if the first decoding
# failed. This is the strict version of the LFRC -> FRC disctionary.
#
# This maps the LFRC in the LRP to the minimal FRC that will be
# accepted

STRICT_TOLERATED_LFRC: Dict[FRC, FRC] = {FRC.FRC0: FRC.FRC1,
                                         FRC.FRC1: FRC.FRC2,
                                         FRC.FRC2: FRC.FRC3,
                                         FRC.FRC3: FRC.FRC4,
                                         FRC.FRC4: FRC.FRC5,
                                         FRC.FRC5: FRC.FRC6,
                                         FRC.FRC6: FRC.FRC7,
                                         FRC.FRC7: FRC.FRC7,
                                         }

# The relaxed version of the LFRC -> FRC dictionary
RELAXED_TOLERATED_LFRC: Dict[FRC, FRC] = {
    FRC.FRC0: FRC.FRC7,
    FRC.FRC1: FRC.FRC7,
    FRC.FRC2: FRC.FRC7,
    FRC.FRC3: FRC.FRC7,
    FRC.FRC4: FRC.FRC7,
    FRC.FRC5: FRC.FRC7,
    FRC.FRC6: FRC.FRC7,
    FRC.FRC7: FRC.FRC7,
}

# A strict configuration
StrictConfig = Config(
    max_dnp_deviation=0.1,
    tolerated_dnp_dev=30,
    tolerated_lfrc=STRICT_TOLERATED_LFRC,
    max_bear_deviation=30,
    search_radius=20,
    geo_weight=0.25,
    frc_weight=0.25,
    fow_weight=0.25,
    bear_weight=0.25,
    fow_standin_score=STRICT_FOW_STAND_IN_SCORE
)

# A relaxed configuration
RelaxedConfig = Config(
    max_dnp_deviation=0.1,
    tolerated_dnp_dev=30,
    tolerated_lfrc=RELAXED_TOLERATED_LFRC,
    search_radius=50,
    geo_weight=0.66,
    frc_weight=0.17,
    fow_weight=0.17,
    bear_weight=0.0,
    fow_standin_score=STRICT_FOW_STAND_IN_SCORE
)

# A configuration meant for decoding within a buffer
BufferConfig = Config(
    candidate_threshold=0,
    max_dnp_deviation=0.2,
    tolerated_dnp_dev=30,
    tolerated_lfrc=STRICT_TOLERATED_LFRC,
    max_bear_deviation=30,
    search_radius=20,
    geo_weight=0.25,
    frc_weight=0.25,
    fow_weight=0.25,
    bear_weight=0.25,
    fow_standin_score=STRICT_FOW_STAND_IN_SCORE
)

# A configuration that considers *any* connected path
# with a reasonable distance.  It ignores FRC, FOW,
# and bearing,
#
# If a decoding fails # with this configuration, it is
# likely that the target maps is either missing road
# segments (most # probable reason) or else has one-way
# road segments  encoded in the wrong direction (relative
# to the source map)
AnyPath = Config(
    min_score=0.0,
    candidate_threshold=0,
    max_dnp_deviation=0.2,
    tolerated_dnp_dev=30,
    tolerated_lfrc=RELAXED_TOLERATED_LFRC,
    max_bear_deviation=180,
    search_radius=20,
    geo_weight=1.0,
    frc_weight=0.0,
    fow_weight=0.0,
    bear_weight=0.0,
    fow_standin_score=STRICT_FOW_STAND_IN_SCORE
)

IgnoreFRC = Config(
    min_score=0.3,
    candidate_threshold=0,
    max_dnp_deviation=0.2,
    tolerated_dnp_dev=30,
    tolerated_lfrc=RELAXED_TOLERATED_LFRC,
    max_bear_deviation=30,
    search_radius=20,
    geo_weight=0.33,
    frc_weight=0.0,
    fow_weight=0.33,
    bear_weight=0.33,
    fow_standin_score=STRICT_FOW_STAND_IN_SCORE
)

IgnoreBearing = Config(
    min_score=0.3,
    candidate_threshold=0,
    max_dnp_deviation=0.2,
    tolerated_dnp_dev=30,
    tolerated_lfrc=STRICT_TOLERATED_LFRC,
    max_bear_deviation=180,
    search_radius=20,
    geo_weight=0.33,
    frc_weight=0.33,
    fow_weight=0.33,
    bear_weight=0,
    fow_standin_score=STRICT_FOW_STAND_IN_SCORE
)

IgnoreFOW = Config(
    min_score=0.3,
    candidate_threshold=0,
    max_dnp_deviation=0.2,
    tolerated_dnp_dev=30,
    tolerated_lfrc=STRICT_TOLERATED_LFRC,
    max_bear_deviation=30,
    search_radius=20,
    geo_weight=0.33,
    frc_weight=0.33,
    fow_weight=0,
    bear_weight=0.33,
    fow_standin_score=RELAXED_FOW_STAND_IN_SCORE
)

IgnorePathLength = Config(
    min_score=0.3,
    candidate_threshold=0,
    max_dnp_deviation=1.0,
    tolerated_dnp_dev=1000,
    tolerated_lfrc=STRICT_TOLERATED_LFRC,
    max_bear_deviation=30,
    search_radius=20,
    geo_weight=0.25,
    frc_weight=0.25,
    fow_weight=0.25,
    bear_weight=0.25,
    fow_standin_score=STRICT_FOW_STAND_IN_SCORE
)
