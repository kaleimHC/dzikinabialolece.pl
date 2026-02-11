from .settings import *  # noqa

# pytest-django needs to know which database to use for tests.
# With --keepdb, Django checks if the DB exists (it does) and skips CREATE DATABASE.
# This avoids PgBouncer's DDL restriction entirely.
DATABASES["default"]["TEST"] = {
    "NAME": "dziki_db",
}
