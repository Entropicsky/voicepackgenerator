"""Change VoScript character_description to Text

Revision ID: aae67b8739de
Revises: 005d4f159baa
Create Date: 2025-04-26 21:22:23.224766

"""
from alembic import op
import sqlalchemy as sa
# Import postgresql dialect for JSONB type
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'aae67b8739de'
down_revision = '005d4f159baa'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands manually written ###
    op.alter_column('vo_scripts', 'character_description',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               type_=sa.Text(), # Change to Text
               existing_nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands manually written ###
    op.alter_column('vo_scripts', 'character_description',
               existing_type=sa.Text(),
               type_=postgresql.JSONB(astext_type=sa.Text()), # Change back to JSONB
               existing_nullable=True)
    # ### end Alembic commands ###
