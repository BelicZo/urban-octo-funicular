# coding=utf-8
# lockbot.py
import uuid

from flask import Flask
from flask import request
import json

from lockbotdb import Changes, Projects
from manager import Manager
from lockstatus_enum import LockStatusEnum

LOCKSTATUS = LockStatusEnum()
app = Flask(__name__)


@app.route('/all-master-branch', methods=['POST'])
def all_master_branch():
    json_str = ""
    if request.method == 'POST':
        (result, text) = check_legality(request)
        if result:
            text = text.strip('\n').split()
            if len(text) == 2:
                lock_type = text[1]
                session = get_session()
                for branch_name in manager.master_branch:
                    projects = session.query(Projects).filter(
                        Projects.branch_name == branch_name).all()
                    if projects:
                        for project in projects:
                            if lock_type == 'lock' and project.lock_status \
                                    == LOCKSTATUS.UN_LOCK:
                                project.lock_status = LOCKSTATUS.MANUAL_LOCK
                            elif lock_type == 'unlock' and project.lock_status\
                                    != LOCKSTATUS.UN_LOCK:
                                project.lock_status = LOCKSTATUS.UN_LOCK
                                project.branch_admin = None
                                handle_change(session, project)
                        json_str = "%s branch locked successfully." % lock_type
                    else:
                        json_str = "%s branch locked failed." % lock_type
                    session.commit()
                session.close()
            else:
                json_str = "input error."
        else:
            json_str = text
        json_res = get_json(json_str)
        return json_res


@app.route('/passchange', methods=['POST'])
def pass_chage():
    if request.method == 'POST':
        (result, text) = check_legality(request)
        if result:
            text = text.strip('\n').split()
            if len(text) == 2:
                change_id = text[1]
                try:
                    session = get_session()
                    change = session.query(Changes).filter(
                        Changes.change_id == change_id).first()
            if not change:
			print "aaaaaaaaaaaaa"
			json_str = "the change id is None."
                    elif not change.is_delete:
			print "bbbbbbbbbbbbb"
                        change.is_delete = True
                        comment = 'recheck'
                        manager.review_comment(comment, 0, change.change_id, change.patchset)
                        session.commit()
                        session.close()
                        json_str = "the change id [%s] passed successfully." % change_id
                    else:
			print "ccccccccccccc"
                        json_str = "the change [%s] had been passed." % change_id
                except Exception as errors:
                    json_str = errors
            else:
                json_str = "input error."
        else:
            json_str = text
        json_res = get_json(json_str)
        return json_res


@app.route('/branch-lock', methods=['POST'])
def branch_lock():
    if request.method == 'POST':
        (result, text) = check_legality(request)
        if result:
            text = text.strip('\n').split()
            if len(text) == 3:
                lock_type = text[1]
                branch_name = text[2]
                if lock_type == 'add':
                    session = get_session()
                    projects = session.query(Projects).filter(
                        Projects.branch_name == branch_name,
                        Projects.lock_status == LOCKSTATUS.UN_LOCK).all()
                    add_status = LOCKSTATUS.MANUAL_LOCK
                elif lock_type == 'remove':
                    session = get_session()
                    projects = session.query(Projects).filter(
                        Projects.branch_name == branch_name).all()
                    add_status = LOCKSTATUS.UN_LOCK
                else:
                    json_str = "input error."
                    json_res = get_json(json_str)
                    return json_res
                try:
                    if projects:
                        for project in projects:
                            project.lock_status = add_status
                            if add_status == 'remove':
                                project.branch_admin = None
                                handle_change(session, project)
                        session.commit()
                        session.close()
                        json_str = "%s branch locked successfully." % lock_type
                    else:
                        json_str = "%s branch locked failed." % lock_type
                except Exception as errors:
                    json_str = errors
            else:
                json_str = "input error."
        else:
            json_str = text
        json_res = get_json(json_str)
        return json_res


@app.route('/project-lock', methods=['POST'])
def project_lock():
    if request.method == 'POST':
        (result, text) = check_legality(request)
        if result:
            text = text.strip('\n').split()
            if len(text) == 3:
                lock_type = text[1]
                project_name = text[2]
                if lock_type == 'add':
                    session = get_session()
                    projects = session.query(Projects).filter(
                        Projects.project_name == project_name,
                        Projects.lock_status == LOCKSTATUS.UN_LOCK).all()
                    add_status = LOCKSTATUS.MANUAL_LOCK
                elif lock_type == 'remove':
                    session = get_session()
                    projects = session.query(Projects).filter(
                        Projects.project_name == project_name).all()
                    add_status = LOCKSTATUS.UN_LOCK
                else:
                    json_str = "input error."
                    json_res = get_json(json_str)
                    return json_res
                try:
                    if projects:
                        for project in projects:
                            project.lock_status = add_status
                            if add_status == 'remove':
                                project.branch_admin = None
                                handle_change(session, project)
                        session.commit()
                        session.close()
                        json_str = "%s project locked successfully." % lock_type
                    else:
                        json_str = "%s project locked failed." % lock_type
                except Exception as errors:
                    json_str = errors
            else:
                json_str = "input error."
        else:
            json_str = text
        json_res = get_json(json_str)
        return json_res


@app.route('/pb-lock', methods=['POST'])
def pb_lock():
    if request.method == 'POST':
        (result, text) = check_legality(request)
        if result:
            text = text.strip('\n').split()
            if len(text) == 4:
                lock_type = text[1]
                project_name = text[2]
                branch_name = text[3]
                if lock_type == 'add':
                    session = get_session()
                    projects = session.query(Projects).filter(
                        Projects.project_name == project_name,
                        Projects.branch_name == branch_name,
                        Projects.lock_status == LOCKSTATUS.UN_LOCK).all()
                    add_status = LOCKSTATUS.MANUAL_LOCK
                elif lock_type == 'remove':
                    session = get_session()
                    projects = session.query(Projects).filter(
                        Projects.project_name == project_name,
                        Projects.branch_name == branch_name).all()
                    add_status = LOCKSTATUS.UN_LOCK
                else:
                    json_str = "input error."
                    json_res = get_json(json_str)
                    return json_res
                try:
                    if projects:
                        for project in projects:
                            project.lock_status = add_status
                            if add_status == 'remove':
                                project.branch_admin = None
                                handle_change(session, project)
                        session.commit()
                        session.close()
                        json_str = "%s project and branch locked successfully." % lock_type
                    else:
                        json_str = "%s project and branch locked failed." % lock_type
                except Exception as errors:
                    json_str = errors
            else:
                json_str = "input error."
        else:
            json_str = text
        json_res = get_json(json_str)
        return json_res


@app.route('/branch-admin', methods=['POST'])
def branch_admin():
    if request.method == 'POST':
        (result, text) = check_legality(request)
        if result:
            text = text.strip('\n').split()
            if len(text) == 4:
                op_type = text[1]
                branch_name = text[2]
                admin_str = text[3]
                print op_type, branch_name, admin_str
                if op_type != 'add' and op_type != 'remove':
                    json_str = "input error."
                    json_res = get_json(json_str)
                    return json_res
                try:
                    session = get_session()
                    admin_list = admin_str.split(',')
                    projects = session.query(Projects).filter(
                        Projects.branch_name == branch_name).all()
                    if projects:
                        if op_type == 'add':
                            add_admin(projects, admin_list)
                        elif op_type == 'remove':
                            remove_admin(projects, admin_list)
                        session.commit()
                        session.close()
                        json_str = "%s branch admin successfully." % op_type
                    else:
                        json_str = "%s branch admin failed." % op_type
                except Exception as errors:
                    json_str = errors
            else:
                json_str = "input error."
        else:
            json_str = text
        json_res = get_json(json_str)
        return json_res


@app.route('/project-admin', methods=['POST'])
def project_admin():
    if request.method == 'POST':
        (result, text) = check_legality(request)
        if result:
            text = text.strip('\n').split()
            if len(text) == 4:
                op_type = text[1]
                project_name = text[2]
                admin_str = text[3]
                if op_type != 'add' and op_type != 'remove':
                    json_str = "input error."
                    json_res = get_json(json_str)
                    return json_res
                try:
                    session = get_session()
                    admin_list = admin_str.split(',')
                    projects = session.query(Projects).filter(
                        Projects.project_name == project_name).all()
                    if projects:
                        if op_type == 'add':
                            add_admin(projects, admin_list)
                        elif op_type == 'remove':
                            remove_admin(projects, admin_list)
                        session.commit()
                        session.close()
                        json_str = "%s project admin successfully." % op_type
                    else:
                        json_str = "%s project admin failed." % op_type
                except Exception as errors:
                    json_str = errors
            else:
                json_str = "input error."
        else:
            json_str = text
        json_res = get_json(json_str)
        return json_res


@app.route('/pb-admin', methods=['POST'])
def pb_admin():
    if request.method == 'POST':
        (result, text) = check_legality(request)
        if result:
            text = text.strip('\n').split()
            if len(text) == 5:
                op_type = text[1]
                project_name = text[2]
                branch_name = text[3]
                admin_str = text[4]
                if op_type != 'add' and op_type != 'remove':
                    json_str = "input error."
                    json_res = get_json(json_str)
                    return json_res
                try:
                    session = get_session()
                    admin_list = admin_str.split(',')
                    projects = session.query(Projects).filter(
                        Projects.project_name == project_name,
                        Projects.branch_name == branch_name).all()
                    if projects:
                        if op_type == 'add':
                            add_admin(projects, admin_list)
                        elif op_type == 'remove':
                            remove_admin(projects, admin_list)
                        session.commit()
                        session.close()
                        json_str = "%s project and branch admin successfully." % op_type
                    else:
                        json_str = "%s project and branch admin failed." % op_type
                except Exception as errors:
                    json_str = errors
            else:
                json_str = "input error."
        else:
            json_str = text
        json_res = get_json(json_str)
        return json_res


@app.route('/add-project', methods=['POST'])
def add_project():
    if request.method == 'POST':
        (result, text) = check_legality(request)
        if result:
            text = text.strip('\n').split()
            if len(text) == 3:
                project_name = text[1]
                branch_name = text[2]
                session = get_session()
                project = session.query(Projects).filter(
                    Projects.project_name == project_name,
                    Projects.branch_name == branch_name).first()
                if not project:
                    project = Projects(uid=str(uuid.uuid4()),
                                       project_name=project_name,
                                       branch_name=branch_name)
                    session.add(project)
                    session.commit()
                    session.close()
                    json_str = "add project successfully."
                else:
                    json_str = "the project already exist."
            else:
                json_str = "input error."
        else:
            json_str = text
        json_res = get_json(json_str)
        return json_res


@app.route('/', methods=['POST'])
def hello():
    json_str = "hello dev"
    json_res = get_json(json_str)
    return json_res


@app.route('/lock-help', methods=['POST'])
def show_cmd_list():
    json_str = u"""
    分支上锁/解锁
    branch-lock [type] [branch_name]

    项目上锁/解锁
    project-lock [type] [project_name]

    指定项目和分支上锁/解锁
    pb-lock [type] [project_name] [branch_name]

    分支合入人增加/移除
    branch-admin [type] [branch_name] [admin]

    项目合入人增加/移除
    project-admin [type] [project_name] [admin]

    指定项目和分支合入人增加/移除
    pb-admin [type] [project_name] [branch_name] [admin]

    新增项目
    add-project [project_name] [branch_name]

    强行合入
    passchange [change_id]

    """
    json_res = get_json(json_str)
    return json_res


def get_json(json_str):
    json_res = {
        "text": json_str
    }
    return json.dumps(json_res)


def check_legality(req):
    result = json.loads(req.data)
    try:
        user_name = result['user_name']
        channel_name = result['channel_name']
        if user_name in manager.special_user and \
           channel_name in manager.channel_list:
            return True, result['text']
        else:
            return False, "You are forbidden to use the API"
    except Exception as errors:
        print errors


def get_session():
    return manager.session()


def add_admin(projects, admin_list):
    for project in projects:
        if project.branch_admin is None:
            branch_admin_list = []
        else:
            branch_admin_list = project.branch_admin.split(',')
        for admin in admin_list:
            if admin not in branch_admin_list:
                branch_admin_list.append(admin)
        branch_admin_str = ""
        for admin in branch_admin_list:
            branch_admin_str += admin + ","
        branch_admin_str = branch_admin_str[:-1]
        project.branch_admin = branch_admin_str


def remove_admin(projects, admin_list):
    for project in projects:
        if project.branch_admin is None:
            return
        branch_admin_list = project.branch_admin.split(',')
        for admin in admin_list:
            if admin in branch_admin_list:
                branch_admin_list.remove(admin)
        branch_admin_str = ""
        for admin in branch_admin_list:
            branch_admin_str += admin + ","
        if branch_admin_str is "":
            branch_admin_str = None
        else:
            branch_admin_str = branch_admin_str[:-1]
        project.branch_admin = branch_admin_str


def handle_change(session, project):
    changes = session.query(Changes).filter(
        Changes.project_id == project.uid,
        Changes.is_delete == False).all()
    for change in changes:
        change.is_delete = True
        comment = 'recheck'
        manager.review_comment(comment, 0, change.change_id, change.patchset)
    session.commit()


if __name__ == '__main__':
    manager = Manager()
    manager.load_config()
    manager.connect_to_db()
    manager.get_gerrit_config()
    app.run(host='0.0.0.0', port=8080)

#　Ｍａｎａｇｅ．ｐｙ
import ConfigParser

import sys

import os
import yaml
from pygerrit.rest import GerritReview
from pygerrit.rest import GerritRestAPI
from requests.exceptions import RequestException
from requests.auth import HTTPDigestAuth
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker


class Manager(object):
    def __init__(self):
        self.special_user = None
        self.channel_list = None
        self.session = None
        self.auth = None
        self.gerrit_url = None
        self.master_branch = None

    def load_config(self):
        path = os.path.join(sys.prefix,
                            'etc/lock-bot/lock_bot_config.yaml')
        with open(path, 'r') as stream:
            try:
                res = yaml.load(stream)
                self.special_user = res['users']
                self.channel_list = res['channel']
            except yaml.YAMLError as errors:
                raise errors

        conf_path = os.path.join(sys.prefix,
                                 'etc/gerrit-lock/config.ini')
        config_parser = ConfigParser.ConfigParser()
        config_parser.read(conf_path)
        self.master_branch = \
            config_parser.get('default', 'master_branch').split(',')

    def connect_to_db(self):
        path = os.path.join(sys.prefix,
                            'etc/gerrit-lock/config.ini')
        config_parser = ConfigParser.ConfigParser()
        config_parser.read(path)
        db_url = config_parser.get('default', 'db_url')
        engine = create_engine(db_url, pool_recycle=3600)
        session_factory = sessionmaker(bind=engine)
        self.session = scoped_session(session_factory)

    def get_gerrit_config(self):
        path = os.path.join(sys.prefix,
                            'etc/gerrit-lock/config.ini')
        config_parser = ConfigParser.ConfigParser()
        config_parser.read(path)
        username = config_parser.get('default', 'username')
        password = config_parser.get('default', 'password')
        self.gerrit_url = config_parser.get('default', 'gerrit_url')
        self.auth = HTTPDigestAuth(username, password)

    def review_comment(self, comment, workflow, change_id, patchset):
        rest = GerritRestAPI(self.gerrit_url, self.auth)
        review = GerritReview(message=comment, labels={"Workflow": workflow})
        try:
            rest.review(change_id, patchset, review)
        except RequestException as errors:
            raise errors
            
            
# lockbotdb.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Boolean
from sqlalchemy import Integer

Base = declarative_base()


class Projects(Base):
    __tablename__ = 'projects'

    uid = Column(String(128), primary_key=True)
    project_name = Column(String(128))
    branch_name = Column(String(128))
    branch_admin = Column(String(128))
    lock_status = Column(Integer(), default=0)


class Changes(Base):
    __tablename__ = 'changes'
    uid = Column(String(128), primary_key=True)
    project_id = Column(String(128))
    project_name = Column(String(128))
    branch_name = Column(String(128))
    change_id = Column(String(128))
    patchset = Column(String(128))
    is_delete = Column(Boolean(), default=False)

    
# setup.cfg   
[metadata]
name = lock-bot
summary = A Python program to listen bot of flowtalk
author = Muzry
author = muzrry@gmail.com
home-page = http://code.huawei.com/lwx366931/lock-bot
description-file = README.md
keywords =
    flowtalk
    lock
    bot
    review

[files]
packages =
    lock_bot

data_files =
    etc/lock-bot =
            etc/lock_bot_config.yaml

[entry_points]
console_scripts =
    lock-bot = lock_bot.lockbot

[pbr]
warnerrors = true
