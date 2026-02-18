#!/bin/bash
# =============================================================================
# Fix pg_hba.conf for PgBouncer MD5 Authentication
# Executed AFTER 01-init.sql by docker-entrypoint
# MASTER_SPEC v2.2 Architecture
# =============================================================================

set -e

PG_HBA="/var/lib/postgresql/data/pg_hba.conf"

echo "=== 02-fix-hba.sh: Configuring MD5 authentication ==="

# Check if pg_hba.conf exists
if [ ! -f "$PG_HBA" ]; then
    echo "ERROR: $PG_HBA not found!"
    exit 1
fi

# Backup original
cp "$PG_HBA" "${PG_HBA}.backup"

# Replace scram-sha-256 with md5 for all connections
# This is required because PgBouncer uses MD5 auth_type
if grep -q "scram-sha-256" "$PG_HBA"; then
    sed -i 's/scram-sha-256/md5/g' "$PG_HBA"
    echo "✓ Changed scram-sha-256 → md5 in pg_hba.conf"
else
    echo "→ No scram-sha-256 found (already md5 or trust)"
fi

# Verify the change
echo ""
echo "Current pg_hba.conf (non-comment lines):"
grep -v "^#" "$PG_HBA" | grep -v "^$" || true

echo ""
echo "=== 02-fix-hba.sh: Complete ==="
echo "→ PostgreSQL will reload config on next connection"
