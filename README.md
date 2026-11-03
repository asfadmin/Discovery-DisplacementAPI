# Discovery-DisplacementAPI
- A FastAPI based Lambda API for querying point based timeseries on OPERA `DISP-S1` data products, querying remote gzipped zarr json stores in S3.

# Overview
## Endpoints

### GET `/`
Returns a basic endpoint status message

### POST `/timeseries`
Returns a json timeseries, mapping file names to a sampled point's `short_wavelength_displacement` value with x & y coordinates, source s3 netcdf4 uri, frame, and dates
```json
{
  "OPERA_L3_DISP-S1_IW_F16942_VV_20160707T015033Z_20160731T015034Z_v1.0_20250617T175432Z.nc":
    {
      "netcdf_uri": "s3:\/\/asf-cumulus-prod-opera-products\/OPERA_L3_DISP-S1_V1\/OPERA_L3_DISP-S1_IW_F16942_VV_20160707T015033Z_20160731T015034Z_v1.0_20250617T175432Z\/OPERA_L3_DISP-S1_IW_F16942_VV_20160707T015033Z_20160731T015034Z_v1.0_20250617T175432Z.nc",
      "bytes": 390070272.0,
      "reference_datetime": "2016-07-07T01:50:33.224",
      "secondary_datetime": "2016-07-31T01:50:34.507",
      "temporal_baseline": 24.0,
      "short_wavelength_displacement": 0.003633976,
      "x": 437565.0,
      "y": 3966615.0,
      "frame": "F16942",
      "is_masked": false, 
    },
    ...,
    "mean":
    {
      "netcdf_uri": null,
      "bytes": 412385371.2757660151,
      "reference_datetime": null,
      "secondary_datetPime": null,
      "temporal_baseline": 1879.8384401114,
      "short_wavelength_displacement": 0.3834199607,
      "x": 437565.0,
      "y": 3966615.0,
      "frame": null,
      "is_masked": null,
    },
    }
}
```

```
params:
    wkt: str
        - A WKT POINT string
    flightDirection: str
        - `ASCENDING` or `DESCENDING` pass
    bucket: str
        - The bucket to query with the zarr stores, ie `asf-cumulus-prod`
    polarization: Polarizations = Polarizations.VV
    frameId: str | None = Field(None, pattern=r'^\d{5}$')
        - Overrides which frame to search
```

### POST `/get_frame_id`
```
params:
    wkt: str
        - A WKT POINT string
    flightDirection: str
        - `ASCENDING` or `DESCENDING` pass
```

# Install and Run Locally
Run pip install from the project's root folder
``` bash
pip install -r src/requirements.txt
```


``` bash
uvicorn src.application:app --port 8080 --reload
```

# Install and Run Test Dependencies Locally

[!IMPORTANT]
To run all tests locally valid AWS credentials are needed for accessing zarr reference stores in EDC

To install test dependencies:
``` bash
pip install -r tests/requirements.txt
```

To run
``` bash
pytest --ignore=tests/yml_tests/test_authorized
```

# Release Workflow

The intended flow from pull request to release is:
`feat/bug-branch`->`test`->`prod`

