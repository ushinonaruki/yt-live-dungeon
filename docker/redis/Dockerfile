FROM redis:7-alpine

HEALTHCHECK --interval=5s --timeout=5s --retries=5 CMD redis-cli ping || exit 1
