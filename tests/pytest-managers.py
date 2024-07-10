import pytest
import requests
import s3fs


test_files = [
    "s3://kfbx-opera-disp-test-bucket/20221107_20221213.unw.nc",
    "s3://kfbx-opera-disp-test-bucket/20221107_20230106.unw.nc",
    "s3://kfbx-opera-disp-test-bucket/20221107_20230130.unw.nc",
    "s3://kfbx-opera-disp-test-bucket/20221107_20230211.unw.nc",
    "s3://kfbx-opera-disp-test-bucket/20221107_20230223.unw.nc",
    "s3://kfbx-opera-disp-test-bucket/20221107_20230319.unw.nc",
    "s3://kfbx-opera-disp-test-bucket/20221107_20230331.unw.nc",
    "s3://kfbx-opera-disp-test-bucket/20221107_20230412.unw.nc",
    "s3://kfbx-opera-disp-test-bucket/20221107_20230506.unw.nc",
    "s3://kfbx-opera-disp-test-bucket/20221107_20230518.unw.nc",
    "s3://kfbx-opera-disp-test-bucket/20221107_20230530.unw.nc",
    "s3://kfbx-opera-disp-test-bucket/20221107_20230705.unw.nc",
    "s3://kfbx-opera-disp-test-bucket/20221107_20230717.unw.nc",
    "s3://kfbx-opera-disp-test-bucket/20221107_20230729.unw.nc",
]

reader_configs = {
    "driver_keywords": {
        "page_buf_size": 32 * 1024**2,
        "rdcc_nbytes": 64,  # 24*1024**2,
        "rdcc_nslots": 641,
    },
    "fsspec_params": {
        "cache_type": "first",  # blockcache
        "block_size": 1024**2 * (2 ** (16)),
    },
}

local_url = 'http://127.0.0.1:8080'
timeseries_endpoint = '/timeseries'

def test_timeseries(**args) -> None:
    test_info = args['test_info']
    params = test_info['params']
    expected_response = test_info['response']

    files = params['files']
    x = params['x']
    y = params['y']

    status_code = expected_response['status_code']

    fsspec_params = None
    driver_keywords = None
    
    if (fsspec_config := test_info.get('fsspec_params')) is not None:
        fsspec_params = fsspec_config
    
    if (driver_kwds := test_info.get('driver_keywords')) is not None:
        driver_keywords = driver_kwds

    test_data = {
        "x": x,
        "y": y,
        "files": files,
        "fsspec_params": fsspec_params,
        'driver_keywords': driver_keywords
    }

    response = requests.post(url=f'{local_url}{timeseries_endpoint}', json=test_data)

    if status_code == 200:
        try:
            response.raise_for_status()
        except BaseException as exc:
            raise Exception(f'timeseries endpoint failed. Reason: {exc}')
    else:
        assert response.status_code == status_code

    body = response.json()

