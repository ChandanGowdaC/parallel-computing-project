FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libboost-all-dev \
    python3 \
    python3-pip \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Copy project files
COPY . /workspace

# Build the project
RUN chmod +x build.sh run.sh && ./build.sh

# Run verification tests
RUN ./run.sh test

# Default command: run baseline smoke test
ENTRYPOINT ["./run.sh"]
