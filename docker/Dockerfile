# The Amoeba hub image (slice 260, D17). Build from the repository root:
#
#   docker build -f docker/Dockerfile -t amoeba-hub .
#
# The image runs `amoeba hub serve` as a non-root user. The hub's config, state and
# backups are three volumes; AMOEBA_HOME is not set, so the config and state homes are
# the user's default ones, which are the first two volumes. A restore is one start
# with a flag added to the entry point: `docker run ... amoeba-hub --from-backup <dir>`.

FROM python:3.13-slim AS build
# The install follows the committed uv.lock exactly (`--locked` fails when it is out of
# date), so the image runs the dependency versions the tests ran against.
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
WORKDIR /src
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
ENV UV_PROJECT_ENVIRONMENT=/opt/amoeba UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
RUN uv sync --locked --no-dev --no-editable

FROM python:3.13-slim
COPY --from=build /opt/amoeba /opt/amoeba

# The examples a person copies into the config volume: hub.yaml, and config.yaml from
# the example block of the config contract.
COPY src/amoeba/hub/hub.yaml.example /usr/share/amoeba/hub.yaml.example
COPY docs/config-contract.md /usr/share/amoeba/config-contract.md

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin amoeba \
    && mkdir -p /home/amoeba/.config/amoeba /home/amoeba/.local/state/amoeba /backups \
    && chown -R amoeba:amoeba /home/amoeba /backups
USER amoeba

# Stderr lines (the serving line, a start-up failure) show up in `docker logs` at once.
ENV PYTHONUNBUFFERED=1 PATH=/opt/amoeba/bin:$PATH
VOLUME ["/home/amoeba/.config/amoeba", "/home/amoeba/.local/state/amoeba", "/backups"]
EXPOSE 8443

# Exec form, so `amoeba hub serve` is PID 1 and gets the SIGTERM `docker stop` sends:
# uvicorn finishes the calls in flight and exits. It reaps no children of its own.
ENTRYPOINT ["amoeba", "hub", "serve"]
