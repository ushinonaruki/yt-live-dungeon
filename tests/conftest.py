import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture(scope="session", autouse=True)
def apply_migrations():
    config = Config("alembic.ini")
    command.upgrade(config, "head")
