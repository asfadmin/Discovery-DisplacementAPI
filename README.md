# Discovery-HDFReaderAPI
- A HDF5 based file reader implemented with FastAPI, made for sampling timeseries from remote HDF5/NetCDF files in s3 containers.

# Install and Run Locally
Run pip install from the project's root folder
```
    pip install -e .
```

```
flask --app src run --host=127.0.0.1 --port=8000
```

# Build and Run Conatiner Locally

First, uncomment the commands for running locally in the Dockerfile. It should look like this:

```Dockerfile
# For Running Locally:
RUN mkdir -p /.aws-lambda-rie && curl -Lo /.aws-lambda-rie/aws-lambda-rie \
https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/latest/download/aws-lambda-rie \
&& chmod +x /.aws-lambda-rie/aws-lambda-rie 

ENTRYPOINT ["/.aws-lambda-rie/aws-lambda-rie", "/usr/local/bin/python", "-m", "awslambdaric"]

# ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
```

The container can be built and ran with:
```bash
docker build -t hdf-reader .
docker run -p 9000:8080 hdf
```

The endpoints can then be invoked using `curl` or a program such as `postman`, with AWS lambda event payloads. Using `curl`, 
```bash
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{"resource": "/", "path": "/", "httpMethod": "GET", "headers": {"header": "value"}}'
```

Using `postman`:

URL: `http://localhost:9000/2015-03-31/functions/function/invocations` </br>
Body: 
```json
{
    "path": "/timeseries",
    "resource": "/timeseries",
    "httpMethod": "POST",
    "headers": {
        "Content-Type": "application/json"
    },
    "body": "{\"wkt\": \"POINT(-121.5048 38.5672)\", \"file_store\": \"s3://opera-disp-tms-dev/extractor/11114.json.gz\"}"
}
```
