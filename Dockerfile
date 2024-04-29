FROM python:3.12

WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./src /code/src
EXPOSE 8080
CMD ["uvicorn", "src.application:app", "--host", "0.0.0.0", "--port", "8080"]