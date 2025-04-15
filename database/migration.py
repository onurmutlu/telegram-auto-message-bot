from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime

# SQLite bağlantısı
sqlite_engine = create_engine('sqlite:///data/users.db')
sqlite_meta = MetaData()
sqlite_meta.reflect(bind=sqlite_engine)
sqlite_session = sessionmaker(bind=sqlite_engine)()

# PostgreSQL bağlantısı
pg_engine = create_engine(os.getenv("DB_CONNECTION"))
pg_meta = MetaData()
pg_meta.reflect(bind=pg_engine)
pg_session = sessionmaker(bind=pg_engine)()

# Grupları aktar
groups_table = sqlite_meta.tables['groups']
new_groups_table = Table('groups', pg_meta, autoload_with=pg_engine)

# SQLite'dan verileri çek
groups = sqlite_session.query(groups_table).all()

# PostgreSQL'e ekle
for group in groups:
    pg_session.execute(
        new_groups_table.insert().values(
            group_id=group.group_id,
            name=group.name,
            join_date=group.join_date,
            # ... diğer sütunlar
        )
    )

pg_session.commit()
