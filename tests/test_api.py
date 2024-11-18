from http import HTTPStatus


def test_root(client):
    response = client.get('/')
    assert response.status_code == HTTPStatus.OK
    assert response.json == {'Status': 'A-Okay'}


def test_get_frame_id(client):
    response = client.post('/get_frame_id', json={'wkt': 'POLYGON(-121.5048 38.5672, -121.5048 38.5672, -121.5048 38.5672, -121.5048 38.5672)'})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json['error'].startswith('Failed to load WKT.')

    response = client.post('/get_frame_id', json={})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json['error'].startswith('Failed to load WKT.')

    response = client.post('/get_frame_id', json={'wkt': 'POINT(0 0)'})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json['error'].startswith('No OPERA-S1 burst frame IDs')

    response = client.post('/get_frame_id', json={'wkt': 'POINT(-121.5048 38.5672)'})
    assert response.status_code == HTTPStatus.OK
    assert response.json == {
        'frame_ids': [9157, 11114, 30714, 36543, 36544],
        'wkt': 'POINT(-121.5048 38.5672)'
    }
