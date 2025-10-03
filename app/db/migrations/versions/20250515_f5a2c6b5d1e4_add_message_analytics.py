"""Mesaj etkinlik analizi ve DM dönüşüm tabloları için migrasyon

Revision ID: f5a2c6b5d1e4
Revises: f4aa9c613b4c
Create Date: 2025-05-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f5a2c6b5d1e4'
down_revision: Union[str, None] = 'f4aa9c613b4c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Mesaj etkinlik tablosunu oluştur
    op.create_table(
        'message_effectiveness',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.BigInteger(), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('views', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('reactions', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('replies', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('forwards', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Mesaj etkinlik indekslerini oluştur
    op.create_index('ix_message_effectiveness_message_id', 'message_effectiveness', ['message_id'], unique=False)
    op.create_index('ix_message_effectiveness_group_id', 'message_effectiveness', ['group_id'], unique=False)
    op.create_index('ix_message_effectiveness_category', 'message_effectiveness', ['category'], unique=False)
    op.create_index('ix_message_effectiveness_sent_at', 'message_effectiveness', ['sent_at'], unique=False)
    
    # DM dönüşüm tablosunu oluştur
    op.create_table(
        'dm_conversions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('conversion_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('source_message_id', sa.Integer(), nullable=True),
        sa.Column('group_id', sa.BigInteger(), nullable=False),
        sa.Column('conversion_type', sa.String(), nullable=False),
        sa.Column('converted_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('message_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('response_time', sa.Float(), server_default=sa.text('0'), nullable=False),
        sa.Column('session_duration', sa.Float(), server_default=sa.text('0'), nullable=False),
        sa.Column('is_successful', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['source_message_id'], ['message_effectiveness.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # DM dönüşüm indekslerini oluştur
    op.create_index('ix_dm_conversions_conversion_id', 'dm_conversions', ['conversion_id'], unique=False)
    op.create_index('ix_dm_conversions_user_id', 'dm_conversions', ['user_id'], unique=False)
    op.create_index('ix_dm_conversions_group_id', 'dm_conversions', ['group_id'], unique=False)
    op.create_index('ix_dm_conversions_conversion_type', 'dm_conversions', ['conversion_type'], unique=False)
    op.create_index('ix_dm_conversions_converted_at', 'dm_conversions', ['converted_at'], unique=False)
    
    # Analitik raporları tablosunu oluştur
    op.create_table(
        'analytics_reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('report_date', sa.Date(), nullable=False),
        sa.Column('report_type', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Rapor indekslerini oluştur
    op.create_index('ix_analytics_reports_report_date', 'analytics_reports', ['report_date'], unique=False)
    op.create_index('ix_analytics_reports_report_type', 'analytics_reports', ['report_type'], unique=False)
    
    # Unique kısıtlama - aynı tarih ve rapor tipi için sadece bir kayıt olabilir
    op.create_index('uix_analytics_reports_date_type', 'analytics_reports', ['report_date', 'report_type'], unique=True)


def downgrade() -> None:
    # Tabloları sil
    op.drop_table('analytics_reports')
    op.drop_table('dm_conversions')
    op.drop_table('message_effectiveness') 