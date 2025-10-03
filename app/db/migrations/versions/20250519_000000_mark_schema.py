"""Mark existing schema as base

Revision ID: 2a1b3c4d5e6f
Revises: f5a2c6b5d1e4
Create Date: 2025-05-19 10:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2a1b3c4d5e6f'
down_revision = 'f5a2c6b5d1e4'  # The last migration's revision ID
branch_labels = None
depends_on = None


def upgrade():
    # This is an empty migration to mark the existing schema as the base
    pass


def downgrade():
    # This is an empty migration to mark the existing schema as the base
    pass
