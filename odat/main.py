import configargparse


p = configargparse.ArgParser(default_config_files=['/Users/dave/pyton/openlr/openlr-webtool-python/config/*.ini', '~/.my_settings'])
p.add('-c', '--config', env_var='ODAT_CONFIG', required=False, is_config_file=True, help='config file path')
p.add('--db', env_var='ODAT_DB', required=False, help='path to target SQLite DB')
p.add('-i', '--input', env_var='ODAT_INFILE', help='path to source JSON containing binary OpenLRs and source linestrings')
p.add('--lines_table', env_var='ODAT_LINES_TABLE', help='SQLite table in target DB containing lines')
p.add('--nodes_table', env_var='ODAT_NODE_TABLE', help='SQLite table in target DB containing nodes')
p.add('--decoder_config', env_var='ODAT_DECODER_CONFIG', help='Decder configuration to use when decoding against target map')
p.add('--mod_spatialite', env_var='ODAT_MOD_SPATIALITE', help='Path to mod_spatialite library')
p.add('--target_crs', env_var='ODAT_TARGET_CRS', help='Target CRS for decoding: i.e. EPSG:4326')
p.add('--buffer', env_var='ODAT_BUFFER', help='Size of buffer in meters to construct around source geometry')
p.add('--lrp_radius', env_var='ODAT_LRP_RADIUS', help='Search radius around LRP')
p.add('-v', '--verbose',env_var='ODAT_VERBOSE', help='Turn on debugging', action='store_true')

options = p.parse_args()

print(options)
print("----------")
print(p.format_help())
print("----------")
print(p.format_values())    # useful for logging where different settings came from
print(options.verbose)