FROM python:3.9.6-alpine

WORKDIR /usr/src/mdcproject

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apk add --no-cache gcc musl-dev linux-headers
COPY requirements.txt .
RUN /usr/local/bin/python -m pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .

ENTRYPOINT ["/usr/src/mdcproject/entrypoint.sh"]

