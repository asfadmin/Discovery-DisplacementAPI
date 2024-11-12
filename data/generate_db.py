import sqlite3
from pathlib import Path
from typing import Iterable

import boto3
from osgeo import ogr
from shapely import from_wkt

OPERA_DB_PATH = Path(__file__).parent / 'opera-s1-disp-0.5.0.post1.dev20-2d.gpkg'


def download_frame_db(db_path: Path = OPERA_DB_PATH) -> Path:
    if db_path.exists():
        return db_path
    print('Downloading frame database...')
    s3 = boto3.client('s3')
    s3.download_file('opera-disp-tms-dev', db_path.name, str(db_path))


def frames_to_geo(frames: Iterable[tuple], output_path: str, of='Parquet'):
    driver = ogr.GetDriverByName(of)
    data_source = driver.CreateDataSource(output_path)
    layer = data_source.CreateLayer('frames', geom_type=ogr.wkbPolygon)
    field_list = [
        ('frame_id', ogr.OFTInteger),
        ('epsg', ogr.OFTInteger),
        ('relative_orbit_number', ogr.OFTInteger),
        ('orbit_direction', ogr.OFTString),
    ]
    for field_name, field_type in field_list:
        layer.CreateField(ogr.FieldDefn(field_name, field_type))

    for frame in frames:
        frame_id, epsg, relative_orbit_number, orbit_pass, _, _, geom = frame
        polygon = from_wkt(geom)
        feature = ogr.Feature(layer.GetLayerDefn())
        val_dict = {
            'frame_id': frame_id,
            'epsg': epsg,
            'relative_orbit_number': relative_orbit_number,
            'orbit_direction': orbit_pass,
        }
        for field_name, field_value in val_dict.items():
            feature.SetField(field_name, field_value)

        geom = ogr.CreateGeometryFromWkt(polygon.wkt)
        feature.SetGeometry(geom)
        layer.CreateFeature(feature)

    data_source = None


def get_frames() -> Iterable[tuple]:
    download_frame_db()
    query = (
        'SELECT fid as frame_id, epsg, relative_orbit_number, orbit_pass, '
        '       is_land, is_north_america, ASText(GeomFromGPB(geom)) AS wkt '
        'FROM frames '
        'WHERE is_north_america = ?'
        'AND is_land = ?'
    )
    params = [1, 1]
    with sqlite3.connect(OPERA_DB_PATH) as con:
        con.enable_load_extension(True)
        con.load_extension('mod_spatialite')
        cursor = con.cursor()
        cursor.execute(query, params)
        frames = cursor.fetchall()
    return frames


def create_frame_file(out_path, of='GeoJSON'):
    frames = get_frames()
    frames_to_geo(frames, out_path, of)


if __name__ == '__main__':
    create_frame_file('frames.geojson', of='GeoJSON')
