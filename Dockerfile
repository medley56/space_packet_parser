# Python version with which to test (must be supported and available on dockerhub)
ARG BASE_IMAGE_PYTHON_VERSION

FROM python:${BASE_IMAGE_PYTHON_VERSION:-3.11}-slim AS test

USER root

ENV INSTALL_LOCATION=/opt/space_packet_parser
WORKDIR $INSTALL_LOCATION

# Create virtual environment and permanently activate it for this image
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
# This adds not only the venv python executable but also all installed entrypoints to the PATH
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
# Upgrade pip to the latest version because poetry uses pip in the background to install packages
RUN pip install --upgrade pip

RUN apt-get update
RUN apt-get install -y curl

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python -
# Add poetry to path
ENV PATH="$PATH:/root/.local/bin"

COPY space_packet_parser $INSTALL_LOCATION/space_packet_parser
COPY tests $INSTALL_LOCATION/tests
COPY pylintrc $INSTALL_LOCATION
COPY pyproject.toml $INSTALL_LOCATION
# LICENSE.txt is referenced by pyproject.toml
COPY LICENSE.txt $INSTALL_LOCATION
# README.md is referenced by pyproject.toml
COPY README.md $INSTALL_LOCATION
# CITATION.cff is referenced by pyproject.toml
COPY CITATION.cff $INSTALL_LOCATION

# Ensure pip is upgraded
RUN pip install --upgrade pip

# Install all dependencies (including dev deps) specified in pyproject.toml
RUN poetry install

ENTRYPOINT pytest --cov-report=xml:coverage.xml \
    --cov-report=term \
    --cov=space_packet_parser \
    --junitxml=junit.xml \
    tests


FROM test AS lint

ENTRYPOINT pylint space_packet_parser