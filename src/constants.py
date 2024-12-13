from enum import Enum


class Polarizations(str, Enum):
    VV = 'VV'
    VH = 'VH'


fsspec_params = {
    'default_cache_type': 'blockcache',
    'default_block_size': 64 * 1024 * 1024,  # could be bigger
}
