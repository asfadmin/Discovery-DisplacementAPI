import pytest

from src.lambda_handler import app

@pytest.fixture
def client():
    with app.test_client() as test_client:
        yield test_client
