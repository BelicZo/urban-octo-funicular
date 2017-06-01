from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Integer
Base = declarative_base()


class Projects(Base):
    __tablename__ = 'gerritlock_projects'

    uid = Column(String(128), primary_key=True)
    project_name = Column(String(128))
    branch_name = Column(String(128))
    branch_admin = Column(String(128))
    lock_status = Column(Integer(), default=0)


class Changes(Base):
    __tablename__ = 'gerritlock_changes'
    uid = Column(String(128), primary_key=True)
    project_id = Column(String(128))
    project_name = Column(String(128))
    branch_name = Column(String(128))
    change_id = Column(String(128))
    patchset = Column(String(128))
    is_delete = Column(Boolean(), default=False)
