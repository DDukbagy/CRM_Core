import os, subprocess, sys
sys.path.insert(0, ".")
import logging; logging.disable(logging.CRITICAL)
from sqlalchemy.engine.url import make_url
from app.core.config import settings
u = make_url(settings.DATABASE_URL).set(drivername="postgresql", query={"sslmode": "require"})
r = subprocess.run(["docker", "run", "--rm", "--network", "host", "-e", "PGURL", "postgres:17", "sh", "-c",
                    'pg_dump "$PGURL" --schema=public --schema-only --no-owner --no-privileges'],
                   env={**os.environ, "PGURL": u.render_as_string(hide_password=False)}, stdout=open(sys.argv[1], "w"), stderr=subprocess.PIPE, text=True)
print("pg_dump exit:", r.returncode)
