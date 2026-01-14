#!/usr/bin/env python3
"""
Fetch OSM data for GWR predictors (forests, water, buildings, roads)
for Białołęka district and insert into PostGIS.
"""

import requests
import json
import psycopg2
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
import sys

# Białołęka bounding box
BBOX = "52.28,20.95,52.38,21.08"  # south,west,north,east
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Database connection
DB_CONFIG = {
    "dbname": "dziki_db",
    "user": "dziki",
    "password": "dziki_dev_password",
    "host": "db",
    "port": 5432
}


def fetch_overpass(query):
    """Fetch data from Overpass API."""
    print(f"  Fetching from Overpass...")
    response = requests.post(OVERPASS_URL, data={"data": query}, timeout=120)
    response.raise_for_status()
    return response.json()


def elements_to_geometries(elements):
    """Convert Overpass elements to Shapely geometries."""
    geometries = []

    for el in elements:
        try:
            if el["type"] == "way" and "geometry" in el:
                coords = [(node["lon"], node["lat"]) for node in el["geometry"]]
                if len(coords) >= 3 and coords[0] == coords[-1]:
                    # Closed way = polygon
                    from shapely.geometry import Polygon
                    geom = Polygon(coords)
                elif len(coords) >= 2:
                    # Open way = linestring
                    from shapely.geometry import LineString
                    geom = LineString(coords)
                else:
                    continue

                geometries.append({
                    "osm_id": el.get("id"),
                    "tags": el.get("tags", {}),
                    "geometry": geom
                })

            elif el["type"] == "node" and "lat" in el and "lon" in el:
                from shapely.geometry import Point
                geom = Point(el["lon"], el["lat"])
                geometries.append({
                    "osm_id": el.get("id"),
                    "tags": el.get("tags", {}),
                    "geometry": geom
                })

        except Exception as e:
            print(f"  Warning: Could not process element {el.get('id')}: {e}")
            continue

    return geometries


def insert_forests(conn, geometries):
    """Insert forest geometries into osm_forests table."""
    cur = conn.cursor()
    count = 0

    for g in geometries:
        if not g["geometry"].is_valid:
            g["geometry"] = g["geometry"].buffer(0)

        wkt = g["geometry"].wkt
        name = g["tags"].get("name", "")

        cur.execute("""
            INSERT INTO osm_forests (osm_id, name, geom)
            VALUES (%s, %s, ST_GeomFromText(%s, 4326))
        """, (g["osm_id"], name, wkt))
        count += 1

    conn.commit()
    cur.close()
    return count


def insert_water(conn, geometries):
    """Insert water geometries into osm_water table."""
    cur = conn.cursor()
    count = 0

    for g in geometries:
        if not g["geometry"].is_valid:
            g["geometry"] = g["geometry"].buffer(0)

        wkt = g["geometry"].wkt
        name = g["tags"].get("name", "")
        waterway = g["tags"].get("waterway", g["tags"].get("natural", ""))

        cur.execute("""
            INSERT INTO osm_water (osm_id, name, waterway, geom)
            VALUES (%s, %s, %s, ST_GeomFromText(%s, 4326))
        """, (g["osm_id"], name, waterway, wkt))
        count += 1

    conn.commit()
    cur.close()
    return count


def insert_buildings(conn, geometries):
    """Insert building geometries into osm_buildings table."""
    cur = conn.cursor()
    count = 0

    for g in geometries:
        if not g["geometry"].is_valid:
            g["geometry"] = g["geometry"].buffer(0)

        wkt = g["geometry"].wkt
        building_type = g["tags"].get("building", "yes")

        cur.execute("""
            INSERT INTO osm_buildings (osm_id, building_type, geom)
            VALUES (%s, %s, ST_GeomFromText(%s, 4326))
        """, (g["osm_id"], building_type, wkt))
        count += 1

    conn.commit()
    cur.close()
    return count


def insert_roads(conn, geometries):
    """Insert road geometries into osm_roads table."""
    cur = conn.cursor()
    count = 0

    for g in geometries:
        if not g["geometry"].is_valid:
            continue  # Skip invalid linestrings

        wkt = g["geometry"].wkt
        highway = g["tags"].get("highway", "")
        name = g["tags"].get("name", "")

        cur.execute("""
            INSERT INTO osm_roads (osm_id, highway, name, geom)
            VALUES (%s, %s, %s, ST_GeomFromText(%s, 4326))
        """, (g["osm_id"], highway, name, wkt))
        count += 1

    conn.commit()
    cur.close()
    return count


def main():
    print("=" * 60)
    print("OSM Predictor Data Fetcher for Białołęka")
    print("=" * 60)

    # Connect to database
    print("\nConnecting to PostGIS...")
    conn = psycopg2.connect(**DB_CONFIG)
    print("Connected.")

    # 1. FORESTS
    print("\n[1/4] Fetching FORESTS (landuse=forest, natural=wood)...")
    forest_query = f"""
    [out:json][bbox:{BBOX}];
    (
      way["landuse"="forest"];
      way["natural"="wood"];
      relation["landuse"="forest"];
      relation["natural"="wood"];
    );
    out geom;
    """
    data = fetch_overpass(forest_query)
    geometries = elements_to_geometries(data.get("elements", []))
    count = insert_forests(conn, geometries)
    print(f"  Inserted {count} forest polygons.")

    # 2. WATER
    print("\n[2/4] Fetching WATER (natural=water, waterway=*)...")
    water_query = f"""
    [out:json][bbox:{BBOX}];
    (
      way["natural"="water"];
      way["waterway"];
      relation["natural"="water"];
    );
    out geom;
    """
    data = fetch_overpass(water_query)
    geometries = elements_to_geometries(data.get("elements", []))
    count = insert_water(conn, geometries)
    print(f"  Inserted {count} water features.")

    # 3. BUILDINGS (sample - może być dużo)
    print("\n[3/4] Fetching BUILDINGS (building=*)...")
    building_query = f"""
    [out:json][bbox:{BBOX}];
    way["building"];
    out geom;
    """
    data = fetch_overpass(building_query)
    geometries = elements_to_geometries(data.get("elements", []))
    count = insert_buildings(conn, geometries)
    print(f"  Inserted {count} buildings.")

    # 4. ROADS
    print("\n[4/4] Fetching ROADS (highway=*)...")
    road_query = f"""
    [out:json][bbox:{BBOX}];
    way["highway"];
    out geom;
    """
    data = fetch_overpass(road_query)
    geometries = elements_to_geometries(data.get("elements", []))
    count = insert_roads(conn, geometries)
    print(f"  Inserted {count} roads.")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    cur = conn.cursor()
    for table in ["osm_forests", "osm_water", "osm_buildings", "osm_roads"]:
        cur.execute(f"SELECT count(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  {table}: {count} features")
    cur.close()

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
