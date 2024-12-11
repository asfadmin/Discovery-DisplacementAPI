import os
import pathlib
import requests
import yaml

local_url = 'http://127.0.0.1:8000'
timeseries_endpoint = '/timeseries'


def test_timeseries(**args) -> None:
    test_info = args['test_info']
    params = test_info['params']
    expected_response = test_info['response']

    file_store = params['file_store']
    wkt = params['wkt']

    status_code = expected_response['status_code']

    fsspec_params = None
    driver_keywords = None

    if (fsspec_config := test_info.get('fsspec_params')) is not None:
        fsspec_params = fsspec_config

    if (driver_kwds := test_info.get('driver_keywords')) is not None:
        driver_keywords = driver_kwds

    test_data = {
        'wkt': wkt,
        'file_store': file_store,
        'fsspec_params': fsspec_params,
        'driver_keywords': driver_keywords,
    }

    response = requests.post(url=f'{local_url}{timeseries_endpoint}', json=test_data)

    if status_code == 200:
        try:
            response.raise_for_status()
        except BaseException as exc:
            raise Exception(f'timeseries endpoint failed. Reason: {exc}')
    else:
        assert (
            response.status_code == status_code
        ), f'Expected error code {status_code}, got response code {response.status_code}, "{response.text}"'

    expected_output = expected_response.get('expected_output')

    if expected_output is not None:
        expected_output = _get_resource(expected_output)
        body = response.json()

        assert sorted(body) == sorted(expected_output), f'Expected {expected_output}, got {body}'


# Finds and loads file from yml_tests/Resouces/ if loaded field ends with .yml/yaml extension
def _get_resource(yml_file):
    if isinstance(yml_file, str):
        if yml_file.endswith(('.yml', '.yaml')):
            base_path = pathlib.Path(__file__).parent.resolve()
            with open(os.path.join(base_path, 'yml_tests', 'resources', yml_file), 'r') as f:
                try:
                    return yaml.safe_load(f)
                except yaml.YAMLError as exc:
                    print(exc)
    elif isinstance(yml_file, list):  # check if it's a list of yml files
        if len(yml_file) > 0:
            if isinstance(yml_file[0], str):
                if yml_file[0].endswith(('.yml', '.yaml')):
                    return [_get_resource(file) for file in yml_file]

    return yml_file