FROM public.ecr.aws/docker/library/python:3.11
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.3 /lambda-adapter /opt/extensions/lambda-adapter
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

RUN apt update \
    && apt install -y gdal-bin libgdal-dev \
    && apt clean \
    && rm -rf /var/lib/apt/lists/*

ARG HOST=127.0.0.1
ENV HOST=${HOST}
ARG PORT=9090
ENV PORT=${PORT}

COPY ./src ./src
COPY ./data ./data

COPY requirements.txt ./requirements.txt

RUN uv pip install --system --upgrade -r ./requirements.txt
RUN python -m pip install awslambdaric

COPY README.md ./README.md

LABEL maintainer="Alaska Satellite Facility Discovery Team <uaf-asf-discovery@alaska.edu>"

RUN mkdir -p /.aws-lambda-rie && curl -Lo /.aws-lambda-rie/aws-lambda-rie \
https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/latest/download/aws-lambda-rie \
&& chmod +x /.aws-lambda-rie/aws-lambda-rie 

ENTRYPOINT ["/.aws-lambda-rie/aws-lambda-rie", "/usr/local/bin/python", "-m", "awslambdaric"]

CMD ["src.lambda_handler.handler"]
