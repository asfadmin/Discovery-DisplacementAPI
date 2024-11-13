FROM public.ecr.aws/docker/library/python:3.12
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.3 /lambda-adapter /opt/extensions/lambda-adapter
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ARG HOST=127.0.0.1
ENV HOST=${HOST}
ARG PORT=8080
ENV PORT=${PORT}

RUN apt update \
    && apt install -y gdal-bin libgdal-dev \
    && apt clean \
    && rm -rf /var/lib/apt/lists/*

COPY ./src/requirements.txt ./
RUN uv pip install --system --no-cache-dir --upgrade -r ./requirements.txt

COPY README.md ./README.md

COPY ./src ./src
COPY ./data ./data

LABEL maintainer="Alaska Satellite Facility Discovery Team <uaf-asf-discovery@alaska.edu>"

CMD exec uvicorn --host $HOST --port=$PORT src.application:app
