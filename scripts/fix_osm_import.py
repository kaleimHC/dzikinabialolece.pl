#!/usr/bin/env python3
"""
FIX OSM IMPORT - Kompletny skrypt naprawczy

Naprawia:
1. BBOX za wąski (brak zachodu Białołęki)
2. Brakujące warstwy (allotments, meadow, farmland, park, scrub, railway)
3. Dane poza granicą (clip do Białołęki)

Data: 2024-01-11
"""

import requests
import json
import psycopg2
from psycopg2.extras import execute_values
import sys
import time

# =============================================================================
# KONFIGURACJA
# =============================================================================

# POPRAWNY BBOX (granica Białołęki + margines 500m)
# Granica: 20.9124-21.0895, 52.2873-52.3682
BBOX = "52.282,20.905,52.373,21.095"  # south,west,north,east

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT = 180  # sekundy

import os

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "dziki_db"),
    "user": os.getenv("DB_USER", "dziki"),
    "password": os.getenv("DB_PASSWORD", "dziki_dev_password"),
    "host": os.getenv("DB_HOST", "db"),  # "db" w dockerze, "localhost" lokalnie
    "port": int(os.getenv("DB_PORT", 5432))
}

# Warstwy do pobrania/naprawienia
LAYERS = {
    # ISTNIEJĄCE (do re-pobrania z poprawnym BBOX)
    "forests": {
        "table": "osm_forests",
        "query": """
            [out:json][timeout:{timeout}][bbox:{bbox}];
            (
                way["landuse"="forest"];
                way["natural"="wood"];
                relation["landuse"="forest"];
                relation["natural"="wood"];
            );
            out geom;
        """,
        "redownload": True,
        "geometry_type": "polygon"
    },
    "water": {
        "table": "osm_water",
        "query": """
            [out:json][timeout:{timeout}][bbox:{bbox}];
            (
                way["natural"="water"];
                way["waterway"];
                relation["natural"="water"];
            );
            out geom;
        """,
        "redownload": True,
        "geometry_type": "mixed"
    },
    "roads": {
        "table": "osm_roads",
        "query": """
            [out:json][timeout:{timeout}][bbox:{bbox}];
            way["highway"];
            out geom;
        """,
        "redownload": True,
        "geometry_type": "line"
    },

    # NOWE WARSTWY
    "allotments": {
        "table": "osm_allotments",
        "query": """
            [out:json][timeout:{timeout}][bbox:{bbox}];
            (
                way["landuse"="allotments"];
                relation["landuse"="allotments"];
            );
            out geom;
        """,
        "redownload": False,
        "geometry_type": "polygon",
        "create_table": True
    },
    "meadow": {
        "table": "osm_meadow",
        "query": """
            [out:json][timeout:{timeout}][bbox:{bbox}];
            (
                way["landuse"="meadow"];
                relation["landuse"="meadow"];
            );
            out geom;
        """,
        "redownload": False,
        "geometry_type": "polygon",
        "create_table": True
    },
    "farmland": {
        "table": "osm_farmland",
        "query": """
            [out:json][timeout:{timeout}][bbox:{bbox}];
            (
                way["landuse"="farmland"];
                relation["landuse"="farmland"];
            );
            out geom;
        """,
        "redownload": False,
        "geometry_type": "polygon",
        "create_table": True
    },
    "park": {
        "table": "osm_parks",
        "query": """
            [out:json][timeout:{timeout}][bbox:{bbox}];
            (
                way["leisure"="park"];
                relation["leisure"="park"];
            );
            out geom;
        """,
        "redownload": False,
        "geometry_type": "polygon",
        "create_table": True
    },
    "scrub": {
        "table": "osm_scrub",
        "query": """
            [out:json][timeout:{timeout}][bbox:{bbox}];
            way["natural"="scrub"];
            out geom;
        """,
        "redownload": False,
        "geometry_type": "polygon",
        "create_table": True
    },
    "railway": {
        "table": "osm_railway",
        "query": """
            [out:json][timeout:{timeout}][bbox:{bbox}];
            way["railway"="rail"];
            out geom;
        """,
        "redownload": False,
        "geometry_type": "line",
        "create_table": True
    },
}

# =============================================================================
# FUNKCJE POMOCNICZE
# =============================================================================

def fetch_overpass(query, layer_name):
    """Pobierz dane z Overpass API."""
    formatted_query = query.format(timeout=OVERPASS_TIMEOUT, bbox=BBOX)

    print(f"  Wysyłam zapytanie do Overpass API...")
    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": formatted_query},
            timeout=OVERPASS_TIMEOUT + 30
        )
        response.raise_for_status()
        data = response.json()
        elements = data.get("elements", [])
        print(f"  Pobrano {len(elements)} elementów")
        return elements
    except requests.exceptions.Timeout:
        print(f"  BŁĄD: Timeout przy pobieraniu {layer_name}")
        return []
    except Exception as e:
        print(f"  BŁĄD: {e}")
        return []


def elements_to_geometries(elements, geometry_type="polygon"):
    """Konwertuj elementy Overpass na geometrie."""
    from shapely.geometry import Polygon, LineString, Point

    geometries = []

    for el in elements:
        try:
            if el["type"] == "way" and "geometry" in el:
                coords = [(node["lon"], node["lat"]) for node in el["geometry"]]

                if geometry_type == "polygon" or geometry_type == "mixed":
                    if len(coords) >= 4 and coords[0] == coords[-1]:
                        geom = Polygon(coords)
                    elif len(coords) >= 2 and geometry_type == "mixed":
                        geom = LineString(coords)
                    else:
                        continue
                elif geometry_type == "line":
                    if len(coords) >= 2:
                        geom = LineString(coords)
                    else:
                        continue
                else:
                    continue

                if not geom.is_valid:
                    geom = geom.buffer(0)

                geometries.append({
                    "osm_id": el.get("id"),
                    "tags": el.get("tags", {}),
                    "geometry": geom
                })

        except Exception as e:
            continue

    return geometries


def create_table_if_not_exists(conn, table_name, geometry_type="polygon"):
    """Utwórz tabelę jeśli nie istnieje."""
    cur = conn.cursor()

    geom_sql_type = "Geometry" if geometry_type == "polygon" else "LineString" if geometry_type == "line" else "Geometry"

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id SERIAL PRIMARY KEY,
            osm_id BIGINT,
            name TEXT,
            geom geometry({geom_sql_type}, 4326),
            fetched_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # Indeks przestrzenny
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_{table_name}_geom ON {table_name} USING GIST(geom);
    """)

    conn.commit()
    cur.close()
    print(f"  Tabela {table_name} gotowa")


def clear_table(conn, table_name):
    """Wyczyść tabelę."""
    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY;")
    conn.commit()
    cur.close()


def insert_geometries(conn, table_name, geometries):
    """Wstaw geometrie do tabeli."""
    if not geometries:
        return 0

    cur = conn.cursor()
    count = 0

    for g in geometries:
        try:
            wkt = g["geometry"].wkt
            name = g["tags"].get("name", "")

            cur.execute(f"""
                INSERT INTO {table_name} (osm_id, name, geom)
                VALUES (%s, %s, ST_GeomFromText(%s, 4326))
            """, (g["osm_id"], name, wkt))
            count += 1
        except Exception as e:
            continue

    conn.commit()
    cur.close()
    return count


def clip_to_boundary(conn, table_name):
    """Przytnij dane do granicy Białołęki."""
    cur = conn.cursor()

    # Usuń obiekty całkowicie poza granicą
    cur.execute(f"""
        DELETE FROM {table_name} t
        USING boundaries b
        WHERE b.name = 'bialoleka'
        AND NOT ST_Intersects(t.geom, b.geom);
    """)
    deleted = cur.rowcount

    conn.commit()
    cur.close()

    return deleted


def get_table_stats(conn, table_name):
    """Pobierz statystyki tabeli."""
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        cur.close()
        return count
    except:
        cur.close()
        return 0


# =============================================================================
# GŁÓWNA FUNKCJA
# =============================================================================

def main():
    print("=" * 70)
    print("FIX OSM IMPORT - Kompletna naprawa danych OSM")
    print("=" * 70)
    print(f"\nBBOX: {BBOX}")
    print(f"Overpass timeout: {OVERPASS_TIMEOUT}s")

    # Połączenie z bazą
    print("\n[1] Łączenie z bazą danych...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("  Połączono!")
    except Exception as e:
        print(f"  BŁĄD: {e}")
        print("\n  Spróbuj uruchomić skrypt z wnętrza kontenera Docker:")
        print("  docker exec -it dziki-api python /app/scripts/fix_osm_import.py")
        sys.exit(1)

    # Statystyki PRZED
    print("\n[2] Statystyki PRZED naprawą:")
    stats_before = {}
    for layer_name, config in LAYERS.items():
        count = get_table_stats(conn, config["table"])
        stats_before[layer_name] = count
        status = "✓" if count > 0 else "✗"
        print(f"  {status} {config['table']}: {count}")

    # Przetwarzanie warstw
    print("\n[3] Przetwarzanie warstw...")

    for layer_name, config in LAYERS.items():
        print(f"\n--- {layer_name.upper()} ({config['table']}) ---")

        # Sprawdź czy trzeba utworzyć tabelę
        if config.get("create_table"):
            print(f"  Tworzenie tabeli {config['table']}...")
            create_table_if_not_exists(conn, config["table"], config["geometry_type"])

        # Sprawdź czy trzeba ponownie pobrać
        existing_count = get_table_stats(conn, config["table"])

        if existing_count > 0 and not config.get("redownload"):
            print(f"  Tabela już zawiera {existing_count} rekordów, pomijam pobieranie")
            continue

        if config.get("redownload") and existing_count > 0:
            print(f"  Czyszczenie tabeli (re-download)...")
            clear_table(conn, config["table"])

        # Pobierz z Overpass
        print(f"  Pobieranie z Overpass API...")
        elements = fetch_overpass(config["query"], layer_name)

        if not elements:
            print(f"  Brak danych lub błąd")
            continue

        # Konwertuj do geometrii
        print(f"  Konwersja do geometrii...")
        geometries = elements_to_geometries(elements, config["geometry_type"])
        print(f"  Skonwertowano {len(geometries)} geometrii")

        # Wstaw do bazy
        print(f"  Wstawianie do bazy...")
        inserted = insert_geometries(conn, config["table"], geometries)
        print(f"  Wstawiono {inserted} rekordów")

        # Pauza między zapytaniami (uprzejmość dla Overpass)
        time.sleep(2)

    # Clip do granic
    print("\n[4] Przycinanie do granic Białołęki...")

    for layer_name, config in LAYERS.items():
        table = config["table"]
        count_before = get_table_stats(conn, table)

        if count_before == 0:
            continue

        deleted = clip_to_boundary(conn, table)
        count_after = get_table_stats(conn, table)

        if deleted > 0:
            print(f"  {table}: usunięto {deleted} obiektów poza granicą ({count_before} → {count_after})")
        else:
            print(f"  {table}: wszystkie obiekty wewnątrz granicy ({count_after})")

    # Statystyki PO
    print("\n[5] Statystyki PO naprawie:")
    print("-" * 50)
    print(f"{'Warstwa':<20} {'PRZED':>10} {'PO':>10} {'ZMIANA':>10}")
    print("-" * 50)

    for layer_name, config in LAYERS.items():
        count_after = get_table_stats(conn, config["table"])
        count_before = stats_before.get(layer_name, 0)
        change = count_after - count_before
        change_str = f"+{change}" if change > 0 else str(change)

        print(f"{config['table']:<20} {count_before:>10} {count_after:>10} {change_str:>10}")

    print("-" * 50)

    # Zamknij połączenie
    conn.close()

    print("\n" + "=" * 70)
    print("ZAKOŃCZONO!")
    print("=" * 70)
    print("\nNastępne kroki:")
    print("1. Uruchom: python scripts/recalculate_features.py")
    print("2. Lub w Django: python manage.py recalculate_voronoi_features")


if __name__ == "__main__":
    main()
