import json
import logging
from typing import Dict, Set

import configargparse
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from shapely import wkb, LineString
from webtool.geotools.geotool_3857 import GeoTool_3857
from webtool.geotools.geotool_4326 import GeoTool_4326
from webtool.map_databases.tomtom_sqlite import TomTomMapReaderSQLite

from odat.analysis_result import AnalysisResult
from odat.decoder_configs import StrictConfig, RelaxedConfig
from .analyzer import Analyzer
from time import perf_counter_ns

def build_results_table(results: Dict[str, Set[str]], count: int) -> Table:
    table = Table(title="OpenLR decoding analysis results")

    table.add_column("Result", justify="right", style="cyan", no_wrap=True)
    table.add_column("Count", style="magenta")
    table.add_column("% of total", justify="right", style="green")

    for k, v in results.items():
        if len(v) == 0:
            continue
        table.add_row(str(k), str(len(v)), f"{100.0 * len(v) / count: .02f}%")

    return table
def build_stats_table(total_frac: float, count: int, elapsed: float) -> Table:
    table = Table(title="Run statistics")
    table.show_header = False

    table.add_row("OpenLRs processed", str(count))
    table.add_row("Average % within buffer", f"{100.0 * total_frac / count:.02f}%")
    table.add_row("Elapsed time", f"{elapsed/1_000_000_000:.04f} secs")

    return table
def print_results(results: Dict[str, Set[str]], count: int, total_frac: float, elapsed: float):
    results_table = build_results_table(results, count)
    stats_table = build_stats_table(total_frac, count, elapsed)


    panel = Panel.fit(
        Columns([results_table, stats_table]),
        width=180,
        title="My Panel",
        border_style="red",
        title_align="left",
        padding=(1, 2),
    )


    console = Console()
    console.print(panel)
    #console.print(table)


def parse_cli_args():
    p = configargparse.ArgParser(
        default_config_files=[
            "/Users/dave/pyton/openlr/openlr-webtool-python/config/*.ini",
            "~/.my_settings",
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
        help="GeosConcaveHull() ratio [0.0..1.0]. Smaller means more accurate map_extent but slower execution.  "
        "Negative value means simple BBOX)",
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


def setup_logging(verbose: bool):
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p",
        level=logging.DEBUG if verbose else logging.WARN,
    )


def get_geo_tool(crs: str):
    match crs.upper():
        case "EPSG:4326":
            return GeoTool_4326()
        case "EPSG:3857":
            return GeoTool_3857()
        case _:
            raise ValueError(
                f"Unknown target CRS: {crs}.  Must be one of [EPSG:4326, EPSG:3857]"
            )


def get_config(config: str):
    match config.upper():
        case "STRICTCONFIG":
            return StrictConfig
        case "RELAXEDCONFIG":
            return RelaxedConfig
        case _:
            raise ValueError(
                f"Unknown decoder configuration: {config}.  Must be one of ["
                f"StrictConfig, RelaxedConfig]"
            )


def main():
    start = perf_counter_ns()
    options = parse_cli_args()

    setup_logging(options.verbose)
    geo_tool = get_geo_tool(options.target_crs)
    config = get_config(options.decoder_config)

    rdr = TomTomMapReaderSQLite(
        db_filename=options.db,
        mod_spatialite=options.mod_spatialite,
        lines_table=options.lines_table,
        nodes_table=options.nodes_table,
        geo_tool=geo_tool,
        config=config,
    )

    dat: Analyzer = Analyzer(
        map_reader=rdr,
        buffer_radius=int(options.buffer),
        lrp_radius=int(options.lrp_radius),
        concavehull_ratio=float(options.concavehull_ratio),
    )

    count: int = 0
    total_frac: float = 0.0
    results: Dict[AnalysisResult, Set[str]] = {k: set() for k in list(AnalysisResult)}

    with open(options.input) as inj:
        j = json.loads(inj.read())
        for loc in j["locations"]:
            try:
                geom1 = loc["geometry"]
                ls = wkb.loads(geom1, hex=True)
                assert isinstance(ls, LineString)
                olr: str = loc["locationReference"]
                res, frac = dat.analyze(olr, ls)
                if olr in results[res]:
                    results[AnalysisResult.DUPLICATE_OPENLR_CODE].add(
                        f"{olr} : Duplicate-{count}"
                    )
                else:
                    results[res].add(olr)
                    total_frac += frac
                count += 1
            except Exception as e:
                results[AnalysisResult.UNKNOWN_ERROR].add(f"{olr} : Error-{e}-{count}")

    new_r = {
        str(k).removeprefix("AnalysisResult."): v
        for k, v in sorted(results.items(), key=lambda x: len(x[1]), reverse=True)
    }
    end = perf_counter_ns()
    print_results(new_r, count, total_frac, end-start)


if __name__ == "__main__":
    main()
