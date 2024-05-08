import logging

import json
import unittest
import cProfile
import pstats
from typing import Set, Dict

from shapely import wkb, LineString

from odat.decoder_configs import StrictConfig, AnyPath
from odat.analysis_result import AnalysisResult
from odat.analyzer import Analyzer
from webtool.geotools.geotool_4326 import GeoTool_4326
from webtool.map_databases.tomtom_sqlite import TomTomMapReaderSQLite


def single(test_olr, input_file, db_file):
    rdr = TomTomMapReaderSQLite(
        db_filename=db_file,
        mod_spatialite="/opt/homebrew/lib/mod_spatialite",
        lines_table="links",
        nodes_table="junctions",
        geo_tool=GeoTool_4326(),
        config=StrictConfig,
    )
    dat = Analyzer(map_reader=rdr, buffer_radius=20)
    with open(input_file) as inj:
        j = json.loads(inj.read())
        for loc in j["locations"]:
            geom1 = loc["geometry"]
            ls = wkb.loads(geom1, hex=True)
            assert isinstance(ls, LineString)
            olr: str = loc["locationReference"]
            if olr == test_olr:
                logging.basicConfig(level=logging.DEBUG)
                _, res, frac = dat.analyze(olr, ls)
                print(res, frac)


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.test_data = {}
        # with open("/Users/dave/projects/python/openlr/data/lux-orbis-flow.json") as inj:
        with open(
            "/Users/dave/projects/python/openlr/data/hris/umd-mnr-flow.json"
        ) as inj:
            # with open("/Users/dave/projects/python/openlr/data/isr-orbis-flow.json") as inj:
            j = json.loads(inj.read())
            for loc in j["locations"]:
                geom1 = loc["geometry"]
                ls = wkb.loads(geom1, hex=True)
                assert isinstance(ls, LineString)
                olr: str = loc["locationReference"]
                self.test_data[olr] = ls

    def test_src_is_tgt(self):
        geom1 = "000000000200000028401803F141205BC04048C7FC6540CC7940180410B630A9154048C7F91E646F15401804284DFCE3154048C7F583A53B8E4018044284DFCE314048C7EEF5EC80C74018045A1CAC08314048C7E8BC169C244018047ECFE9B7BF4048C7E0DED288CE401804D2B2BFDB4D4048C7D07C84B5DD4018051EB851EB854048C7C3B4F61672401805681ECD4AA14048C7B83CF2CF964018062F5989DF114048C79ABF338716401806E6D9BE4CD74048C78088509BFA40180771C970F7BA4048C76F2A5A469D401807E7C06E19B94048C7620EE8D10F401808754F3775B84048C753F7CED9174018090D5A5B96294048C74538EF34D740180A57A786C2274048C7256FFC115E40180AB8A5CE5B424048C71BEF49CF5740180ADD590C0AD04048C717ACC4EF8940180AEFB2AAE2974048C715B573EAB340180B2E9CCB7D414048C70DD82FD75E40180B923A29C77A4048C6FF6D33094240180BE8BC169C244048C6F102363B2540180C1D29DC725C4048C6E685DB76B440180C39FFD60E954048C6DFF822BBED40180C5436B8F9B14048C6D916872B0240180C764ADFF8234048C6CF41F212D740180C8B439581064048C6C6BCE8533B40180C9AFE1DA7B14048C6BF3387160940180CAAB8A5CE5B4048C6B65A9A804940180CBA732DF5064048C6A6F3F52FC240180CBD1244A6224048C69B280F12C240180CAAB8A5CE5B4048C680F12C27A640180CAAB8A5CE5B4048C67913E8145140180CB5350092CD4048C66FE718A86D40180CFE9B7BF1E94048C64ECE9A2C6740180D10F51AC9B04048C6469D7342EE40180D4801F751054048C62E09FE868340180D57BC7F77AF4048C626809D495240180D6A161E4F764048C621EA35936040180D844D013A934048C61C044284E0"
        ls = wkb.loads(geom1, hex=True)
        assert isinstance(ls, LineString)
        rdr = TomTomMapReaderSQLite(
            db_filename="/Users/dave/projects/python/openlr/data/lux-orbis.db",
            mod_spatialite="/opt/homebrew/anaconda3/envs/openlr/lib/mod_spatialite",
            lines_table="links",
            nodes_table="junctions",
            geo_tool=GeoTool_4326(),
            config=StrictConfig,
        )
        Analyzer(map_reader=rdr, buffer_radius=20).analyze(
            "CwRE+CM+jxNMHgOn+kYTHg==", ls
        )

    def test_src_is_not_tgt(self):
        rdr = TomTomMapReaderSQLite(
            db_filename="/Users/dave/projects/python/openlr/data/lux-osm.db",
            mod_spatialite="/opt/homebrew/anaconda3/envs/openlr/lib/mod_spatialite",
            lines_table="links",
            nodes_table="junctions",
            geo_tool=GeoTool_4326(),
            config=StrictConfig,
        )
        olr = "CwRE+CM+jxNMHgOn+kYTHg=="
        assert olr in self.test_data
        ls = self.test_data[olr]
        Analyzer(map_reader=rdr, buffer_radius=20).analyze(olr, ls)

    def test_src_is_not_tgt2(self):
        # set logging level to DEBUG
        # logging.basicConfig(level=logging.DEBUG)
        rdr = TomTomMapReaderSQLite(
            db_filename="/Users/dave/projects/python/openlr/data/lux-osm.db",
            mod_spatialite="/opt/homebrew/anaconda3/envs/openlr/lib/mod_spatialite",
            lines_table="links",
            nodes_table="junctions",
            geo_tool=GeoTool_4326(),
            config=StrictConfig,
        )
        olr = "CwRTJyMzRgEYJ/OUAAsBCg=="
        assert olr in self.test_data
        ls = self.test_data[olr]
        res = Analyzer(map_reader=rdr, buffer_radius=20).analyze(olr, ls)
        # ensure the location reference is entirely within the buffer
        print(res)

    def test_decode_within_buffer(self):
        # set logging level to DEBUG
        logging.basicConfig(level=logging.DEBUG)
        rdr = TomTomMapReaderSQLite(
            db_filename="/Users/dave/projects/python/openlr/data/lux-osm.db",
            mod_spatialite="/opt/homebrew/anaconda3/envs/openlr/lib/mod_spatialite",
            lines_table="links",
            nodes_table="junctions",
            geo_tool=GeoTool_4326(),
            config=StrictConfig,
        )
        olr = "CwR4ayNd9xPyKfi5+VMbIwM="
        assert olr in self.test_data
        ls = self.test_data[olr]
        res = Analyzer(map_reader=rdr, buffer_radius=20).analyze(olr, ls)
        print(res)

    def test_decode_within_buffer2(self):
        # set logging level to DEBUG
        logging.basicConfig(level=logging.DEBUG)
        rdr = TomTomMapReaderSQLite(
            db_filename="/Users/dave/projects/python/openlr/data/lux-osm.db",
            mod_spatialite="/opt/homebrew/anaconda3/envs/openlr/lib/mod_spatialite",
            lines_table="links",
            nodes_table="junctions",
            geo_tool=GeoTool_4326(),
            config=AnyPath,
        )
        olr = "CwR1ayNg7xtjPgiGCj4bLwE="
        assert olr in self.test_data
        ls = self.test_data[olr]
        res = Analyzer(map_reader=rdr, buffer_radius=20).analyze(olr, ls)
        print(res)

    def test_decode_weird(self):
        # set logging level to DEBUG
        logging.basicConfig(level=logging.DEBUG)
        rdr = TomTomMapReaderSQLite(
            db_filename="/Users/dave/projects/python/openlr/data/hris/umd-orbis.db",
            mod_spatialite="/opt/homebrew/anaconda3/envs/openlr/lib/mod_spatialite",
            lines_table="links",
            nodes_table="junctions",
            geo_tool=GeoTool_4326(),
            config=StrictConfig,
        )
        olr = "C8kiHxukmRp8HPo0A6gbCw=="
        assert olr in self.test_data
        ls = self.test_data[olr]
        res = Analyzer(map_reader=rdr, buffer_radius=20).analyze(olr, ls)
        assert True

    def test_bulk(self):

        # logging.basicConfig(level=logging.DEBUG)
        results: Dict[AnalysisResult, Set[str]] = {}

        rdr = TomTomMapReaderSQLite(
            # db_filename="/Users/dave/projects/python/openlr/data/lux-osm.db",
            # db_filename="/Users/dave/projects/python/openlr/data/lux-orbis.db",
            db_filename="/Users/dave/projects/python/openlr/data/hris/umd-orbis.db",
            #db_filename="/Users/dave/projects/python/openlr/data/deu-orbis.db",
            mod_spatialite="/opt/homebrew/anaconda3/envs/openlr/lib/mod_spatialite",
            lines_table="links",
            nodes_table="junctions",
            geo_tool=GeoTool_4326(),
            config=StrictConfig,
        )
        dat = Analyzer(map_reader=rdr, buffer_radius=20)
        count: int = 0
        cumulative_frac: float = 0.0
        for olr, ls in self.test_data.items():
            _, res, frac = dat.analyze(olr, ls)
            if res == AnalysisResult.OUTSIDE_MAP_BOUNDS:
                print(f"ignoring location reference {olr} is outside the map bounds")
                continue
            if res not in results:
                results[res] = set()
            results[res].add(olr)
            cumulative_frac += frac
            count += 1

        for k, v in results.items():
            print(k, len(v))
        print(
            f"average location fraction within buffer: {100.0 * cumulative_frac / count: .02f}%"
        )
        print(f"accuracy: {100.0 * len(results[AnalysisResult.OK]) / count: .02f}%")

    def test_profile_bulk(self):

        with cProfile.Profile() as profile:
            results: Dict[AnalysisResult, Set[str]] = {}
            rdr = TomTomMapReaderSQLite(
                db_filename="/Users/dave/projects/python/openlr/data/isr-mnr.db",
                # db_filename="/Users/dave/projects/python/openlr/data/lux-orbis.db",
                # db_filename="/Users/dave/projects/python/openlr/data/hris/umd-orbis.db",
                mod_spatialite="/opt/homebrew/lib/mod_spatialite",
                lines_table="links",
                nodes_table="junctions",
                geo_tool=GeoTool_4326(),
                config=StrictConfig,
            )
            dat = Analyzer(map_reader=rdr, buffer_radius=20)
            for olr, ls in self.test_data.items():
                res = dat.analyze(olr, ls)
                if res not in results:
                    results[res] = set()
                results[res].add(olr)

            for k, v in results.items():
                print(k, len(v))

            (
                pstats.Stats(profile)
                .strip_dirs()
                .sort_stats(pstats.SortKey.CUMULATIVE)
                .print_stats()
            )

    def test_1(self):
        single(
            test_olr="CwUClSL9WgEIhBWeFSUBdbtE",
            input_file="/Users/dave/projects/python/openlr/data/deu-incident.json",
            db_file="/Users/dave/projects/python/openlr/data/deu-mnr-dseg.db",
        )


if __name__ == "__main__":
    unittest.main()
