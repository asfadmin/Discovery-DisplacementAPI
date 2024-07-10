FROM public.ecr.aws/lambda/python:3.12

WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY README.md ./README.md
COPY setup.py ./setup.py
COPY ./src /code/src
RUN python3 -m pip install -U --no-cache-dir .

ENV OPEN_TO_IP="127.0.0.1"
ENV OPEN_TO_PORT=9000
EXPOSE ${OPEN_TO_PORT}

ENTRYPOINT [ "python3", "code/src/application.py" ]
