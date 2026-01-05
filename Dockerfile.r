# =============================================================================
# Dockerfile.r - R Worker for Spatial Analytics
# MASTER_SPEC v2.2 Architecture
# =============================================================================

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
    'sp' \
), repos='https://cloud.r-project.org/')"

# Working directory
WORKDIR /app

# Copy spatialWarsaw package (local)
COPY spatialWarsaw/ /app/spatialWarsaw/

# Install spatialWarsaw from local source
RUN R -e "install.packages('/app/spatialWarsaw', repos=NULL, type='source')"

# Copy R scripts
COPY r_scripts/ /app/r_scripts/

# Environment variables (overridden by docker-compose)
ENV DB_HOST=pgbouncer
ENV DB_PORT=6432
ENV DB_NAME=dziki_db
ENV DB_USER=dziki_user
ENV DB_PASSWORD=dziki_dev_password
ENV OMP_NUM_THREADS=1

# Default command - SAFE: just show available scripts
# NEVER run destructive scripts by default!
# Use: docker-compose run --rm worker-r Rscript /app/r_scripts/<script>.R
CMD ["bash", "-c", "echo 'R Worker ready. Available scripts:' && ls /app/r_scripts/*.R && echo '' && echo 'Usage: docker-compose run --rm worker-r Rscript /app/r_scripts/<script>.R'"]
