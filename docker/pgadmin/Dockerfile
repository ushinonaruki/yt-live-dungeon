FROM dpage/pgadmin4:9.17

HEALTHCHECK --interval=10s --timeout=5s --retries=6 --start-period=30s CMD wget -q -O - http://localhost/misc/ping || exit 1
