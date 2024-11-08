FROM public.ecr.aws/docker/library/python:3.12-slim
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.3 /lambda-adapter /opt/extensions/lambda-adapter
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
ENV HOST=0.0.0.0
ENV PORT=8080

COPY ./src/requirements.txt ./
RUN uv pip install --system --no-cache-dir --upgrade -r ./requirements.txt

COPY README.md ./README.md

COPY ./src ./src

LABEL maintainer="Alaska Satellite Facility Discovery Team <uaf-asf-discovery@alaska.edu>"

CMD exec uvicorn --host $HOST --port=$PORT src.application:app
