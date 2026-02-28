# Dockerfile.r - R Worker for Spatial Analytics

FROM rocker/geospatial:4.3.2

LABEL maintainer="Dziki na Bialolece"
LABEL description="R worker for spatial econometrics (GWR, ETA, tessellation)"

# System dependencies for PostGIS connectivity
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# R packages
RUN R -e "install.packages(c( \
    'RPostgres', \
    'DBI', \
    'spdep', \
    'sp', \
    'spatialreg' \
), repos='https://cloud.r-project.org/')"

# Working directory
WORKDIR /app

# Copy spatialModel package (local adaptation)
COPY spatialModel/ /app/spatialModel/

# Install spatialModel from local source
RUN R -e "install.packages('/app/spatialModel', repos=NULL, type='source')"

# Copy R scripts
COPY r_scripts/ /app/r_scripts/

# Environment variables — non-secret defaults only.
# DB_PASSWORD must be supplied at runtime via docker-compose env_file or -e flag.
# NEVER bake credentials into the image.
ENV DB_HOST=pgbouncer \
    DB_PORT=6432 \
    DB_NAME=dziki_db \
    DB_USER=dziki_user \
    DB_PASSWORD="" \
    OMP_NUM_THREADS=1

# Default command - SAFE: just show available scripts
# NEVER run destructive scripts by default!
# Use: docker-compose run --rm worker-r Rscript /app/r_scripts/<script>.R
CMD ["bash", "-c", "echo 'R Worker ready. Available scripts:' && ls /app/r_scripts/*.R && echo '' && echo 'Usage: docker-compose run --rm worker-r Rscript /app/r_scripts/<script>.R'"]
