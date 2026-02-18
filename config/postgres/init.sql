-- =============================================================================
-- PostgreSQL Init Script - Dziki na Białołęce
-- Executed on first container startup
-- =============================================================================

-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Verify PostGIS
SELECT PostGIS_Version();

-- =============================================================================
-- Schema will be created by Django migrations
-- This file only ensures PostGIS is ready
-- =============================================================================
