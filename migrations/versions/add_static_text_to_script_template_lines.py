"""Add static_text to vo_script_template_lines

Revision ID: 734db99a3f4e
Revises: 3ab799233c3c 
Create Date: 2024-04-29 16:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '734db99a3f4e'
down_revision: Union[str, None] = '3ab799233c3c'  # Update this to point to the migration that exists in prod
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('vo_script_template_lines', schema=None) as batch_op:
        batch_op.add_column(sa.Column('static_text', sa.Text(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('vo_script_template_lines', schema=None) as batch_op:
        batch_op.drop_column('static_text')
    # ### end Alembic commands ### 