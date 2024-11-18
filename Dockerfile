FROM public.ecr.aws/docker/library/python:3.11

RUN apt update \
    && apt install -y gdal-bin libgdal-dev \
    && apt clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install -r ./requirements.txt
RUN python -m pip install awslambdaric

COPY ./src ./src
COPY ./data ./data

COPY README.md ./README.md

LABEL maintainer="Alaska Satellite Facility Discovery Team <uaf-asf-discovery@alaska.edu>"

RUN python -c 'import rasterio, shapely, geopandas'

# For Running Locally:
# RUN mkdir -p /.aws-lambda-rie && curl -Lo /.aws-lambda-rie/aws-lambda-rie \
# https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/latest/download/aws-lambda-rie \
# && chmod +x /.aws-lambda-rie/aws-lambda-rie 

# ENTRYPOINT ["/.aws-lambda-rie/aws-lambda-rie", "/usr/local/bin/python", "-m", "awslambdaric"]

ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]

CMD [ "src.lambda_handler.handler" ]
