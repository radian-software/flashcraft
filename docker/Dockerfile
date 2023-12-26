FROM ubuntu:22.04 AS base

RUN apt-get update && apt-get install -y python3-pip python3-venv tini && rm -rf /var/lib/apt/lists/*
RUN pip3 install "poetry>=1.7,<1.8"

RUN useradd -m -r -p! flashcraft
USER flashcraft

RUN python3 -m venv /home/flashcraft/venv
ENV VIRTUAL_ENV=/home/flashcraft/venv
ENV PATH=/home/flashcraft/venv/bin:$PATH

FROM base AS runtime

USER root
RUN apt-get update && apt-get install -y openjdk-8-jre-headless openjdk-17-jre-headless && rm -rf /var/lib/apt/lists/*
USER flashcraft

RUN mkdir /home/flashcraft/src
WORKDIR /home/flashcraft/src
COPY pyproject.toml poetry.lock /home/flashcraft/src/
RUN poetry install --no-root

COPY flashcraft/ /home/flashcraft/src/flashcraft/

ENTRYPOINT ["tini", "--"]
CMD ["python3", "-u", "-m", "flashcraft.runtime"]

FROM base AS adminpanel

RUN mkdir /home/flashcraft/src
WORKDIR /home/flashcraft/src
COPY pyproject.toml poetry.lock /home/flashcraft/src/
RUN poetry install --no-root

COPY flashcraft/ /home/flashcraft/src/flashcraft/

ENTRYPOINT ["tini", "--"]
CMD ["gunicorn", "-b", "0.0.0.0:8080", "--access-logfile=-", "-R", "flashcraft.adminpanel:app"]
EXPOSE 8080
