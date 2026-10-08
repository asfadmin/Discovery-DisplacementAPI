import pytest


def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        '--use-uat',
        action='store_true',
        dest='use_uat',
        default=False,
        help="'use-uat': Set if the test cases should run against UAT deployment",
    )
