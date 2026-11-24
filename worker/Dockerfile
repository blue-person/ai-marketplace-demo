FROM debian:trixie-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ make libcurl4-openssl-dev nlohmann-json3-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY Makefile ./
COPY src ./src
RUN make
CMD ["/src/robot"]
