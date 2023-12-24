FROM ubuntu:22.04 AS code

RUN apt-get update && apt-get install -y python3-pip python3-venv tini && rm -rf /var/lib/apt/lists/*
RUN pip3 install "poetry>=1.7,<1.8"

RUN useradd -m -r -p! flashcraft
USER flashcraft

RUN python3 -m venv /home/flashcraft/venv
ENV VIRTUAL_ENV=/home/flashcraft/venv
ENV PATH=/home/flashcraft/venv/bin:$PATH

RUN mkdir /home/flashcraft/src
WORKDIR /home/flashcraft/src
COPY pyproject.toml poetry.lock /home/flashcraft/src/
RUN poetry install --no-root

COPY flashcraft/ /home/flashcraft/src/flashcraft/

FROM code AS adminpanel

ENTRYPOINT ["tini", "--"]
CMD ["gunicorn", "-b", "0.0.0.0:8080", "--access-logfile=-", "-R", "flashcraft.adminpanel.app:app"]
EXPOSE 8080
