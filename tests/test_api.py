from http import HTTPStatus


def test_root(client):
    response = client.get('/')
    assert response.status_code == HTTPStatus.OK
    assert response.json == {'Status': 'A-Okay'}


def test_timeseries(client):
    assert False


def test_get_frame_id(client):
    assert False
