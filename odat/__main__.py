import configargparse
from odat.run_analyzer import run_parallel_analyzer


def parse_cli_args():
    p = configargparse.ArgParser(
        default_config_files=[
            "./*.ini",
            "./configs/*.ini",
            "~/.config/odat.ini",
        ]
    )
    p.add(
        "-c",
        "--config",
        env_var="ODAT_CONFIG",
        required=False,
        is_config_file=True,
        help="config file path",
    )
    p.add("--db", env_var="ODAT_DB", required=False, help="path to target SQLite DB")
    p.add(
        "-i",
        "--input",
        env_var="ODAT_INFILE",
        help="path to source JSON containing binary OpenLRs and source linestrings",
    )
    p.add(
        "--lines_table",
        env_var="ODAT_LINES_TABLE",
        help="SQLite table in target DB containing lines",
    )
    p.add(
        "--nodes_table",
        env_var="ODAT_NODE_TABLE",
        help="SQLite table in target DB containing nodes",
    )
    p.add(
        "--decoder_config",
        env_var="ODAT_DECODER_CONFIG",
        help="Decder configuration to use when decoding against target map",
    )
    p.add(
        "--mod_spatialite",
        env_var="ODAT_MOD_SPATIALITE",
        help="Path to mod_spatialite library",
    )
    p.add(
        "--output_dir",
        env_var="ODAT_OUTPUT_DIR",
        help="Directory to write output files",
    )
    p.add(
        "--output_file",
        env_var="ODAT_OUTPUT_FILE",
        help="File to write output JSON",
    )
    p.add(
        "--target_crs",
        env_var="ODAT_TARGET_CRS",
        help="Target CRS for decoding: i.e. EPSG:4326",
    )
    p.add(
        "--buffer",
        env_var="ODAT_BUFFER",
        help="Size of buffer in meters to construct around source geometry",
    )
    p.add(
        "--concavehull_ratio",
        env_var="ODAT_CONCAVEHULL_RATIO",
        help="GeosConcaveHull() ratio [0.0..]. Smaller means more accurate map_extent but slower execution.  "
        ">= 1.0 means simple BBOX)",
    )

    p.add(
        "--num_threads",
        env_var="ODAT_NUM_THREADS",
        help="Number of parallel threads to use",
    )

    p.add("--lrp_radius", env_var="ODAT_LRP_RADIUS", help="Search radius around LRP")

    p.add(
        "-v",
        "--verbose",
        env_var="ODAT_VERBOSE",
        help="Turn on debugging",
        action="store_true",
    )

    return p.parse_args()

def main():
    options = parse_cli_args()
    run_parallel_analyzer(options)


if __name__ == "__main__":
    main()
