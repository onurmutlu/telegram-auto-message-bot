"""initial_migration

Revision ID: f4aa9c613b4c
Revises: 
Create Date: 2025-05-03 01:52:52.403656

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'f4aa9c613b4c'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Önce groups tablosunu oluştur (diğer tablolar buna foreign key referansı verecek)
    op.create_table(
        'groups',
        sa.Column('group_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('username', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('join_date', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_message', sa.DateTime(), nullable=True),
        sa.Column('message_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('member_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('error_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('last_error', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('permanent_error', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('is_target', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('retry_after', sa.DateTime(), nullable=True),
        sa.Column('is_admin', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('is_public', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('invite_link', sa.String(), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('last_active', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('group_id')
    )
    
    # debug_bot_users tablosu
    op.create_table(
        'debug_bot_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('username', sa.String(), nullable=True),
        sa.Column('first_name', sa.String(), nullable=True),
        sa.Column('last_name', sa.String(), nullable=True),
        sa.Column('access_level', sa.String(), nullable=True),
        sa.Column('first_seen', sa.DateTime(), nullable=True),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('is_developer', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('is_superuser', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    
    # settings tablosu
    op.create_table(
        'settings',
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('key')
    )
    
    # telegram_users tablosu
    op.create_table(
        'telegram_users',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(), nullable=True),
        sa.Column('first_name', sa.String(), nullable=True),
        sa.Column('last_name', sa.String(), nullable=True),
        sa.Column('is_bot', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('is_premium', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('language_code', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('bio', sa.String(), nullable=True),
        sa.Column('first_seen', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_seen', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('is_blocked', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('user_id')
    )
    
    # user_group_relation tablosu
    op.create_table(
        'user_group_relation',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('group_id', sa.BigInteger(), nullable=False),
        sa.Column('joined_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['groups.group_id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['debug_bot_users.user_id'], ),
        sa.PrimaryKeyConstraint('user_id', 'group_id')
    )
    
    # group_members tablosu
    op.create_table(
        'group_members',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('group_id', sa.BigInteger(), nullable=False),
        sa.Column('joined_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_seen', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('is_admin', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('admin_rights', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['groups.group_id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['telegram_users.user_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'group_id', name='unique_user_group')
    )
    
    # group_analytics tablosu
    op.create_table(
        'group_analytics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('group_id', sa.BigInteger(), nullable=False),
        sa.Column('date', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('member_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('message_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('active_users', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('engagement_rate', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('growth_rate', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['groups.group_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # data_mining tablosu
    op.create_table(
        'data_mining',
        sa.Column('mining_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('telegram_id', sa.BigInteger(), nullable=True),
        sa.Column('group_id', sa.BigInteger(), nullable=True),
        sa.Column('type', sa.String(), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('data', sa.String(), nullable=True),
        sa.Column('is_processed', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['groups.group_id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['telegram_users.user_id'], ),
        sa.PrimaryKeyConstraint('mining_id')
    )
    
    # message_tracking tablosu
    op.create_table(
        'message_tracking',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=False),
        sa.Column('group_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('content', sa.String(), nullable=True),
        sa.Column('content_type', sa.String(), server_default=sa.text('text'), nullable=True),
        sa.Column('is_outgoing', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('is_reply', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('reply_to_message_id', sa.Integer(), nullable=True),
        sa.Column('forwards', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('views', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['groups.group_id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['telegram_users.user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Tüm tabloları silme (ters sırayla)
    op.drop_table('message_tracking')
    op.drop_table('data_mining')
    op.drop_table('group_analytics')
    op.drop_table('group_members')
    op.drop_table('user_group_relation')
    op.drop_table('telegram_users')
    op.drop_table('settings')
    op.drop_table('debug_bot_users')
    op.drop_table('groups') 