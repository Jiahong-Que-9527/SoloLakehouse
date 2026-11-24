FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Project 02 runs as a set of single-file CLI tools on Python 3.13 with a
# locked uv environment. The image carries the code, the contract and the
# synthetic test suite; data always comes from mounted local directories.
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev
COPY *.py ./
COPY contracts/ ./contracts/

# No data in the image: the default command is the synthetic suite, which
# needs no Bronze or Silver input and doubles as a smoke test.
CMD ["uv", "run", "--locked", "--no-sync", "python", "-m", "unittest", \
     "discover", "-s", ".", "-p", "test_*.py", "-v"]
