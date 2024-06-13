from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, FilePath, field_validator

"""
This class holds the pydantic sanitized and validated CLI options controlling the ODAT analysis process.
"""

class Options(BaseModel):
    db: FilePath
    input: FilePath
    detailed: Optional[str]
    lines_table: str
    nodes_table: str
    decoder_config: str
    mod_spatialite: str
    output_dir: str
    target_crs: str
    concave_ratio: float = Field(0.5, ge=0.0)
    buffer: int = Field(20, ge=0)
    lrp_radius: int = Field(20, ge=0)
    num_threads: int = Field(1, ge=1)
    verbose: bool = False

    @field_validator("output_dir")
    def check_output_dir(cls, v):
        # check if directory exists, and if not, create it
        t = Path(v)
        if not t.exists():
            t.mkdir(parents=True)
        return v
