import json
import logging
import sqlite3
from multiprocessing import Queue
from time import perf_counter_ns
from typing import Dict, Set, Tuple
import time

from functools import reduce

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from shapely import wkb, LineString, Polygon
from webtool.geotools.geotool_3857 import GeoTool_3857
from webtool.geotools.geotool_4326 import GeoTool_4326
from webtool.map_databases.tomtom_sqlite import TomTomMapReaderSQLite

from odat.analysis_result import AnalysisResult
from odat.decoder_configs import StrictConfig, RelaxedConfig
from .analyzer import Analyzer

import multiprocessing as mp

from .options import Options

POISON_PILL_MSG = "__DONE__"


def build_results_table(results: Dict[str, Set[Tuple[str, float]]], count: int) -> Table:
    table = Table(title="ODAT analysis summary")

    table.add_column("Result", justify="right", style="cyan", no_wrap=True)
    table.add_column("Count", style="magenta")
    table.add_column("% of total", justify="right", style="green")
    table.add_column("% within buffer", justify="right", style="green")

    for k, v in results.items():
        if len(v) == 0:
            continue
        table.add_row(
            str(k),
            str(len(v)),
            f"{(100.0 * len(v) / count) if count > 0 else 0: .02f}%",
            f"{(100.0 * (reduce(lambda accum, x: accum + x[1], v, 0.0)) / len(v)) if len(v) > 0 else 0: .02f}%",
        )

    return table


def build_stats_table(
        total_frac: float,
        count: int,
        elapsed: float,
        map_bounds_time: float,
        analysis_time: float,
) -> Table:
    table = Table(title="Run statistics")
    table.show_header = False

    table.add_row("OpenLRs processed", str(count))
    table.add_row(
        "Average % within buffer",
        f"{(100.0 * total_frac / count) if count > 0 else 0:.02f}%",
    )
    table.add_row(
        "Map boundary calculation time", f"{map_bounds_time / 1_000_000_000:.04f} secs"
    )
    table.add_row("OpenLR analysis time", f"{analysis_time / 1_000_000_000:.04f} secs")
    table.add_row("Total elapsed time", f"{elapsed / 1_000_000_000:.04f} secs")

    return table


def print_results(
        results: Dict[str, Set[Tuple[str, float]]],
        count: int,
        total_frac: float,
        elapsed: float,
        map_bounds_time: float,
        analysis_time: float,
):
    results_table = build_results_table(results, count)
    stats_table = build_stats_table(
        total_frac, count, elapsed, map_bounds_time, analysis_time
    )

    panel = Panel.fit(
        Columns([results_table, stats_table]),
        # width=180,
        title="ODAT Results",
        border_style="red",
        title_align="left",
        padding=(1, 2),
    )

    console = Console()
    console.print(panel)


def load_queue(q, options):
    """
    This loader process reads a file containing the openlr codes and geometries to be analyzed and places each
    code on the worker input queue.  At EOF, it inserts WORKER_COUNT "poison pills" into the queue so
    that each worker receives one and shuts itself down
    """

    with open(options.input) as inj:
        j = json.loads(inj.read())
        for loc in j["locations"]:
            try:
                geom1 = loc["geometry"]
                ls = wkb.loads(geom1, hex=True)
                assert isinstance(ls, LineString)
                olr: str = loc["locationReference"]
                category: str = loc["category"]
                frc: int = int(loc["frc"])
                q.put((olr, ls, category, frc))
            except Exception as e:
                logging.warning(f"Error loading {loc['locationReference']}: {e}")

        for _ in range(int(options.num_threads)):
            q.put(POISON_PILL_MSG)


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


def get_map_bounds(map_reader: TomTomMapReaderSQLite, concavehull_ratio: float):
    try:
        return map_reader.get_map_bounds(concavehull_ratio)
    except sqlite3.DataError as sde:
        logging.warning(f"Unable to calculate concave map bounds: {sde}. "
                        "Re-trying with convex hull (MISSING_OR_MISCONFIGURED_ROAD counts may be inaccurate).")
        return map_reader.get_map_bounds(1.0)


def worker(
        id: int, q_in: Queue, q_out: Queue, options, map_bounds: Polygon, config, geo_tool, verbose: bool
):
    """
    Each worker takes a record off the queue and attempts to decode it.  If it successful, it places a tuple
    containing the code as well as the decoded coordinates on the writer input queue.  If it is unsuccessful,
    it places a FAILED_DECODING_MSG message on the writer's queue.  WHen it sees a poison pill message, it
    places a POISON_PILL_MSG message on the writer queue and terminates.
    """

    setup_logging(verbose)
    error_count = 0
    olr = ""

    def enqueue(olr: str, category: str, frc: int, res: AnalysisResult, frac: float) -> None:
        q_out.put((olr, category, frc, res, frac))

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
        map_bounds=map_bounds,
    )

    logging.info(f"Worker {id} initialized")
    msg = q_in.get()

    while msg != POISON_PILL_MSG:
        try:
            olr, ls, category, frc = msg
            olr, res, frac = dat.analyze(olr, ls)
            enqueue(olr, category, frc, res, frac)
        except Exception as e:
            logging.error(f"Error during analysis of {olr}: {e}")
            enqueue(
                f"{olr} : Error-{e}-{id}-{error_count}",
                AnalysisResult.UNKNOWN_ERROR,
                0.0,
            )
            error_count += 1
        msg = q_in.get()
    q_out.put(msg)
    logging.debug(f"Worker {id} shutting down")


def run_parallel_analyzer(options: Options):
    start = perf_counter_ns()

    setup_logging(options.verbose)
    geo_tool = get_geo_tool(options.target_crs)
    config = get_config(options.decoder_config)

    workers = []
    ctx = mp.get_context("spawn")
    # create the worker and writer queues
    q_in = ctx.Queue(0)
    q_out = ctx.Queue(0)

    # spawn the loader, passing it the worker queue to fill
    loader = ctx.Process(target=load_queue, args=(q_in, options))
    loader.start()
    active_workers = 0

    rdr = TomTomMapReaderSQLite(
        db_filename=options.db,
        mod_spatialite=options.mod_spatialite,
        lines_table=options.lines_table,
        nodes_table=options.nodes_table,
        geo_tool=geo_tool,
        config=config,
    )
    map_bounds_start = perf_counter_ns()
    map_bounds = get_map_bounds(rdr, float(options.concavehull_ratio))
    map_bounds_time = perf_counter_ns() - map_bounds_start

    # spawn the workers
    for i in range(int(options.num_threads)):
        p = ctx.Process(
            target=worker,
            args=(i, q_in, q_out, options, map_bounds, config, geo_tool, options.verbose),
        )
        p.start()
        workers.append(p)
        active_workers += 1

    count: int = 0
    total_frac: float = 0.0
    results: Dict[str, Set[Tuple[str, float]]] = {
        str(k).removeprefix("AnalysisResult."): set() for k in list(AnalysisResult)
    }

    analysis_start = perf_counter_ns()
    output_filename = time.strftime("%Y%m%d-%H%M%S")

    metadict = {
        "input_file": f"{str(options.input)}",
        "output_file": f"{str(output_filename)}.json",
        "buffer_radius": options.buffer,
        "lrp_radius": options.lrp_radius,
        "decoder_config": options.decoder_config,
        "target_crs": options.target_crs,
        "concavehull_ratio": options.concavehull_ratio,
        "db": f"{str(options.db)}",
        "mod_spatialite": options.mod_spatialite,
        "lines_table": options.lines_table,
        "nodes_table": options.nodes_table,
        "num_threads": options.num_threads,
    }
    metadata = json.dumps(metadict)
    first = True

    with open(f"{options.output_dir}/{output_filename}.json", "wt") as outf:
        outf.write(f"""{{"metadata":{metadata}, "locations":[""")

        while active_workers > 0:
            try:
                msg = q_out.get()
                if msg == POISON_PILL_MSG:
                    # Poison pill:  decrement the worker count
                    logging.debug("Worker shutdown detected")
                    active_workers -= 1
                else:
                    olr, category, frc, res, frac = msg
                    res = str(res).removeprefix("AnalysisResult.")
                    rec = json.dumps(
                        {"locationReference": olr, "category": category, "frc": frc, "result": res, "fraction": frac})
                    outf.write(f"{'' if first else ','}{rec}")
                    first = False

                    if (olr, frac) in results[res]:
                        results["DUPLICATE_OPENLR_CODE"].add(
                            (f"{olr} : Duplicate-{count}", 0.0)
                        )
                    else:
                        results[res].add((olr, frac))
                        total_frac += frac
                        count += 1
            except Exception as e:
                results["UNKNOWN_ERROR"].add(
                    (f"{olr} : Error-{e}-{count}", 0.0)
                )
        outf.write("]}")

    analysis_time = perf_counter_ns() - analysis_start
    new_r = {
        k: v
        for k, v in sorted(results.items(), key=lambda x: len(x[1]), reverse=True)
    }
    end = perf_counter_ns()
    print_results(new_r, count, total_frac, end - start, map_bounds_time, analysis_time)
