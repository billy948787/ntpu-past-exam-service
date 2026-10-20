"""reconcile PostgreSQL production baseline

Revision ID: 4d7c2a91b6e3
Revises: 2555095e0ae9
Create Date: 2026-10-20 00:00:00.000000

The first PostgreSQL production database was created from SQLAlchemy metadata
and stamped with this revision during the one-off MySQL import. The revision
file used for that stamp was not preserved in Git. Reintroducing the identifier
as a no-op successor connects that existing database to the maintained Alembic
graph without replaying the historical MySQL-only migrations.
"""

from typing import Sequence, Union


revision: str = "4d7c2a91b6e3"
down_revision: Union[str, None] = "2555095e0ae9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
