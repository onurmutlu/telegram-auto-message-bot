   # database/models.py oluşturun
   
   from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, create_engine
   from sqlalchemy.ext.declarative import declarative_base
   from sqlalchemy.orm import relationship, sessionmaker
   from datetime import datetime
   
   Base = declarative_base()
   
   class Group(Base):
       __tablename__ = 'groups'
       
       group_id = Column(Integer, primary_key=True)
       name = Column(String)
       join_date = Column(DateTime, default=datetime.now)
       last_message = Column(DateTime)
       message_count = Column(Integer, default=0)
       member_count = Column(Integer, default=0)
       error_count = Column(Integer, default=0)
       last_error = Column(String)
       is_active = Column(Boolean, default=True)
       permanent_error = Column(Boolean, default=False)
       is_target = Column(Boolean, default=True)
       retry_after = Column(DateTime)
       created_at = Column(DateTime, default=datetime.now)
       updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)