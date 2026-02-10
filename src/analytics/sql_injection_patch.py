"""
SQL Injection Allowlist Patch - shared validators for safe table-name interpolation.

Import this module wherever f-string SQL with table/grid_type variables is used.
All table name interpolation MUST go through these functions before use in SQL.

Usage:
    from analytics.sql_injection_patch import validate_grid_type, validate_geometry_type, validate_limit

    grid_table = validate_grid_type(grid_type)          # raises ValueError on invalid input
    table      = validate_geometry_type(geometry_type)  # raises ValueError on invalid input
    safe_limit = validate_limit(limit_param)             # returns int, clamped
"""

# Allowlists - add new values here when the schema changes

# Maps user-supplied grid_type string -> exact DB table name.
# Most grid types follow the sightings_gridcell_{suffix} pattern, but grid_500
# lives in research_grid_500m, so map to full table names rather than suffixes.
_VALID_GRID_TYPES: dict[str, str] = {
    "voronoi": "sightings_gridcell_voronoi",
    "square": "sightings_gridcell_square",
    "research": "sightings_gridcell_research",
    "grid_500": "research_grid_500m",
}

# Maps user-supplied geometry_type string -> exact DB table name
_GEOMETRY_TABLE_MAP: dict[str, str] = {
    "grid_500": "research_grid_500m",
    "voronoi": "sightings_gridcell_voronoi",
}

# Absolute cap on LIMIT to prevent runaway queries
_LIMIT_MAX = 10_000
_LIMIT_DEFAULT = 100


def validate_grid_type(grid_type: str) -> str:
    """
    Validate grid_type and return the exact DB table name.

    Returns: full table name (e.g. 'sightings_gridcell_voronoi', 'research_grid_500m')
    Raises: ValueError if grid_type is not in the allowlist
    """
    table = _VALID_GRID_TYPES.get(str(grid_type))
    if table is None:
        allowed = ", ".join(sorted(_VALID_GRID_TYPES.keys()))
        raise ValueError(f"Invalid grid_type {grid_type!r}. Allowed values: {allowed}")
    return table


def validate_geometry_type(geometry_type: str) -> str:
    """
    Validate geometry_type and return the exact DB table name.

    Raises: ValueError if geometry_type is not in the allowlist
    """
    table = _GEOMETRY_TABLE_MAP.get(str(geometry_type))
    if table is None:
        allowed = ", ".join(sorted(_GEOMETRY_TABLE_MAP.keys()))
        raise ValueError(
            f"Invalid geometry_type {geometry_type!r}. Allowed values: {allowed}"
        )
    return table


def validate_limit(
    limit_param, default: int = _LIMIT_DEFAULT, maximum: int = _LIMIT_MAX
) -> int:
    """
    Parse and clamp a LIMIT query parameter to a safe integer.

    Raises: ValueError if limit_param cannot be coerced to a positive int
    """
    try:
        value = int(limit_param)
    except (TypeError, ValueError):
        value = default
    if value < 1:
        value = default
    return min(value, maximum)
