# Discovery-HDFReaderAPI
- A HDF5 based file reader implemented with FastAPI, made for sampling timeseries from remote HDF5/NetCDF files in s3 containers.

# Install and Run Locally
Run pip install from the project's root folder
```
    pip install -e .
```


``` python
uvicorn src.application:app --port 8080

--reload
```