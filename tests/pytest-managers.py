import os
import pathlib
import urllib.parse

import httpx2
import yaml
from fastapi.testclient import TestClient

from src.application import _wrap_wkt, app

timeseries_endpoint = '/timeseries'
client = TestClient(app)
uat_endpoint = 'https://d8itg4twhevb5.cloudfront.net'


def _query_api(endpoint: str, params: dict, method: str, use_uat: bool):
    match method:
        case 'GET':
            p = urllib.parse.urlencode(params)
            return (
                httpx2.get(f'{uat_endpoint}{endpoint}?{p}', timeout=30)
                if use_uat
                else client.get(url=f'{endpoint}?{p}')
            )
        case 'POST':
            return (
                httpx2.post(f'{uat_endpoint}{endpoint}', json=params, timeout=30)
                if use_uat
                else client.post(url=f'{endpoint}', json=params)
            )
        case _:
            raise NotImplementedError(f'Method {method} not implemented')


def test_wkt_wrapping(**args) -> None:
    test_info = args['test_info']
    wkt, wrapped = test_info['wkt'], test_info['wrapped']

    actual, actual_wrapped = _wrap_wkt(wkt)

    assert actual.wkt == wkt, (
        f'Original geometry modified when unwrapping wkt. Expected wkt: {wkt}. Actual: {actual.wkt}'
    )
    assert actual_wrapped.wkt == wrapped, (
        f'Failed to wrap wkt. Expected wkt: {wrapped}. Actual: {actual_wrapped}'
    )


def test_endpoints(**args) -> None:
    test_info = args['test_info']
    params = test_info['params']
    expected_response = test_info['response']
    endpoint = test_info['endpoint']
    method = test_info['method']
    use_uat = args['config'].getoption('use_uat')

    status_code = expected_response['status_code']

    response = _query_api(endpoint, params, method, use_uat)
    if status_code == 200:
        response.raise_for_status()
    else:
        assert response.status_code == status_code, (
            f'Expected error code {status_code}, got response code {response.status_code}, "{response.text}"'
        )

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
    elif isinstance(yml_file, list):  # noqa: SIM102  # check if it's a list of yml files
        if len(yml_file) > 0:  # noqa: SIM102
            if isinstance(yml_file[0], str):  # noqa: SIM102
                if yml_file[0].endswith(('.yml', '.yaml')):
                    return [_get_resource(file) for file in yml_file]

    return yml_file
