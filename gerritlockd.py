#!/usr/bin/python2
# -*- coding: utf-8 -*-

import ConfigParser
import logging
import os
import sys
import time
import requests
import uuid

from threading import Event
from pygerrit.events import CommentAddedEvent
from pygerrit.client import GerritClient
from pygerrit.rest import GerritReview
from pygerrit.error import GerritError
from pygerrit.rest import GerritRestAPI
from requests.auth import HTTPDigestAuth
from pygerrit.events import ErrorEvent
from requests.exceptions import RequestException
from daemon import Daemon
from manager import Manager
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import scoped_session
from sqlalchemy import create_engine
from gerritlockdb import Projects
from gerritlockdb import Changes
from lockstatus_enum import LockStatusEnum

CI_STATE_QUERY_URL = "http://openstack.huawei.com:9000/ci_interface"
SPECIAL_USERS_QUERY_URL = "http://10.162.239.121:8000/latest"
LOCKSTATUS = LockStatusEnum()


class GerritLock(Daemon):
    def __init__(self, pid):
        self.manager = Manager()
        self.projects = None
        self.special_user = None
        self.session = None
        self.master_branch = None
        self.ci_lock = False
        self.branches = None
        super(GerritLock, self).__init__(pid)

    def connect_to_gerrit(self, config_parser):
        # 连接到gerrit
        host = config_parser.get('default', 'host')  # host = review
        while True:
            try:
                gerrit = GerritClient(host)
                """
                ~/.ssh/config文件注明了连接信息
                Host review
                    HostName cloudos-review.huawei.com
                    Port 29418
                    User prolandjarvis
                    IdentityFile ~/.ssh/jarvis
                """
                logging.info("Connected to Gerrit Version[%s]", gerrit.gerrit_version())
                gerrit.start_event_stream()

            except GerritError as errors:
                logging.error("Gerrit error: %s", errors)
                time.sleep(30)
                logging.info("Reconnecting...")
                continue
            else:
                break
        return gerrit

    def loop_event(self, config_parser, gerrit, rest):
        is_block = config_parser.get('default', 'block') == 'True'  # is_block = False
        timeout = config_parser.get('default', 'timeout')  # '30'
        ignore_error = config_parser.get("default", "ignore_error") == "True"  # True
        debug_mode = config_parser.get("default", "debug_mode") == "True"  # False
        debug_project = config_parser.get("default", "debug_project")  # 'dev-test/neutron'
        poll = config_parser.getint("default", "poll")  # 1
        errors = Event()

        try:
            while True:
                event = gerrit.get_event(block=is_block, timeout=timeout)
                if event:
                    logging.info("Event: %s", event)
                    if isinstance(event, ErrorEvent):  # 判断gerrit事件是否是错误事件类型
                        if not ignore_error:
                            logging.error(event.error)
                            errors.set()
                            break
                        if event.error == "Remote server connection closed":
                            gerrit.stop_event_stream()
                            gerrit = self.connect_to_gerrit(config_parser)
                    else:
                        if debug_mode and hasattr(event, 'change') and \
                                event.change.project != debug_project:
                            continue

                        self.handle_event(event, rest)  # 调用  操作事件
                else:
                    if not is_block:
                        time.sleep(poll)
        except KeyboardInterrupt:
            logging.info("Terminated by user")
        finally:
            logging.debug("Stopping event stream...")
            gerrit.stop_event_stream()
        return errors

    def handle_event(self, event, rest):

        if isinstance(event, CommentAddedEvent):
            # TODO CommentAddedEvent ?
            project_name = event.change.project
            branch_name = event.change.branch
            change_id = event.json['change']['number']
            patchset = event.patchset.revision
            author_user = event.author.username
            is_save = False
            for approval in event.approvals:
                if approval.category == 'Workflow' and\
                                    approval.value == '1':
                    fail_department = self.check_ci_lock(rest)

                    result = self.check_locked(project_name, branch_name)
                    comment = u"Error! (Jarvis Bot): "
                    if result == LOCKSTATUS.UN_LOCK:
                        if not self.check_unlock_user(author_user, project_name, branch_name):
                            comment += u"%s无权限合入！" % author_user
                            self.review_comment(comment, rest, -1, change_id, patchset)
                            return
                    if result == LOCKSTATUS.MANUAL_LOCK:
                        if not self.check_user(author_user, project_name, branch_name):
                            is_save = True
                            comment += u"代码库已手动上锁！"
                            break
                    if result == LOCKSTATUS.CI_LOCK:
                        if not self.check_ci_user(author_user, fail_department):
                            is_save = True
                            comment += u"主干冒烟失败，代码库已上锁！"
                            break
                    if result == LOCKSTATUS.TIME_LOCK:
                        if not self.check_user(author_user, project_name, branch_name):
                            is_save = True
                            comment += u"下午三点至第二日八点(周二全天)无法合入代码，代码库已上锁！"
                            break
            if is_save:
                self.save_change(project_name, branch_name, change_id, patchset)
                self.review_comment(comment, rest, -1, change_id, patchset)
            return

    def review_comment(self, comment, rest, workflow, change_id, patchset):
        review = GerritReview(message=comment, labels={"Workflow": workflow})
        try:
            rest.review(change_id, patchset, review)
        except RequestException as errors:
            logging.error("Error: %s", errors)

    def check_unlock_user(self, user, project_name, branch_name):
        session = self.session()
        project = session.query(Projects).filter(
            Projects.project_name == project_name,
            Projects.branch_name == branch_name).first()
        session.close()
        if project.branch_admin is None:
            return True
        elif user in project.branch_admin.split(','):
            return True
        else:
            return False

    def check_user(self, user, project_name, branch_name):
        session = self.session()
        project = session.query(Projects).filter(
                    Projects.project_name == project_name,
                    Projects.branch_name == branch_name).first()
        session.close()
        if project.branch_admin is not None:
            if user in project.branch_admin.split(','):
                return True
        return False

    def check_ci_user(self, user, fail_department):
        response = requests.get(SPECIAL_USERS_QUERY_URL)
        response_data = response.json()
        owners = []
        for owner in response_data['owners']:
            owners.append(owner.split('_')[1])
        if user in owners:
            return True

        for key, users_list in self.special_user['subpm'].items():
            if key in fail_department:
                if user in users_list:
                    return True
        return False

    def check_locked(self, project_name, branch_name):
        session = self.session()
        project = session.query(Projects).filter(
                    Projects.project_name == project_name,
                    Projects.branch_name == branch_name).first()
        session.close()
        if project:
            return project.lock_status
        return

    def save_change(self, project_name, branch_name, change_id, patchset):
        session = self.session()
        project = session.query(Projects).filter(
            Projects.project_name == project_name,
            Projects.branch_name == branch_name).first()
        change = session.query(Changes).filter(
            Changes.change_id == change_id,
            Changes.is_delete == False).first()
        if change:
            change.patchset = patchset
        else:
            new_change = Changes(uid=str(uuid.uuid4()),
                                 project_name=project_name,
                                 branch_name=branch_name,
                                 change_id=change_id,
                                 patchset=patchset,
                                 project_id=project.uid)
            session.add(new_change)
            session.commit()
        session.close()

    def ci_locked(self):
        session = self.session()
        for branch in self.master_branch:
            projects = session.query(Projects).filter(
                Projects.branch_name == branch,
                Projects.lock_status == LOCKSTATUS.UN_LOCK).all()
            for project in projects:
                    project.lock_status = LOCKSTATUS.CI_LOCK
            session.commit()
        session.close()

    def ci_unlock(self, rest):
        session = self.session()
        for branch in self.master_branch:
            projects = session.query(Projects).filter(
                Projects.branch_name == branch,
                Projects.lock_status == LOCKSTATUS.CI_LOCK).all()
            for project in projects:
                project.lock_status = LOCKSTATUS.UN_LOCK
                changes = session.query(Changes).filter(
                    Changes.project_id == project.uid,
                    Changes.is_delete == False).all()
                for change in changes:
                    change.is_delete = True
                    comment = 'recheck'
                    self.review_comment(comment, rest, 0, change.change_id, change.patchset)
            session.commit()
        session.close()

    def check_ci_lock(self, rest):
        request_body = {
            "transport_state": 101,
            "ci_branch": "smoke_ci_test"
        }
        response = requests.post(CI_STATE_QUERY_URL,
                                 json=request_body)
        try:
            response_data = response.json()
            result = response_data['data']['result']
            fail_department = response_data['data']['fail_department']
            if not result:
                if not self.ci_lock:
                    self.ci_locked()
                    self.ci_lock = True
            else:
                if self.ci_lock:
                    self.ci_unlock(rest)
                    self.ci_lock = False
            return fail_department
        except Exception as er:
            logging.error(er)

    def run(self):
        self.special_user = self.manager.load_users()
        # {'admin': ['d00255876', 'm00225990'],
        # 'subpm': {'fi': ['l00329577', 'z00219100'], 'fk': ['z00165808'], 'fn': ['z00241626']},
        # 'special': [{'hocco': ['z00219100', 'm00225990']}]}

        # config_parser读取配置文件
        config_parser = ConfigParser.ConfigParser()
        config_parser.read(os.path.join(sys.prefix,
                                        'etc/gerrit-lock/config.ini'))
        username = config_parser.get('default', 'username')
        # username = prolandjarvis
        password = config_parser.get('default', 'password')
        # password =
        gerrit_url = config_parser.get('default', 'gerrit_url')
        # gerrit_url = http://cloudos-review.huawei.com
        db_url = config_parser.get('default', 'db_url')
        # db_url = "mysql+mysqlconnector://[user]:[password]@[ip]:3306/[database]?charset=utf8"
        is_debug = config_parser.get('default', 'debug') == 'True'  # debug = False
        self.master_branch = config_parser.get("default", "master_branch").split(",")
        # master_branch = master,hw/mitaka,hw/v3.5.6,hw/1.15.1,rpm-hw-master
        self.branches = config_parser.get('default', "branches").split(",")
        # branches = master,hw/mitaka,hw/v3.5.6,hw/1.15.1,rpm-hw-master,hocco,dpgk,caiman,dpdk

        level = logging.DEBUG if is_debug else logging.INFO
        # 日志记录
        if not os.path.exists('/var/log/gerrit-lock'):
            os.mkdir('/var/log/gerrit-lock')

        logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
                            filename='/var/log/gerrit-lock/gerrit-lock.log',
                            level=level)

        try:
            # 连接数据库
            engine = create_engine(db_url, pool_recycle=3600)
            session_factory = sessionmaker(bind=engine)
            self.session = scoped_session(session_factory)
        except Exception as errors:
            raise errors

        # HTTP 摘要式身份认证 requests.get(url, auth=HTTPDigestAuth('user', 'pass')
        auth = HTTPDigestAuth(username, password)
        rest = GerritRestAPI(url=gerrit_url, auth=auth)
        # self.manager.load_projects(rest, self.session, self.branches)

        try:
            gerrit = self.connect_to_gerrit(config_parser)  # 连接gerrit
            if gerrit:
                errors = self.loop_event(config_parser, gerrit, rest)

                if errors.isSet():
                    logging.error("Exited with error")
                    return 1
        except KeyboardInterrupt:
            logging.info("Terminated by user")
            return 1


def main():
    gerrit_lock = GerritLock('/var/run/gerrit-lock.pid')


    if len(sys.argv) < 2:
        gerrit_lock.run()
    elif sys.argv[1] == 'start':
        gerrit_lock.start()
    elif sys.argv[1] == 'stop':
        gerrit_lock.stop()
    elif sys.argv[1] == 'restart':
        gerrit_lock.stop()
        time.sleep(2)
        gerrit_lock.start()

if __name__ == '__main__':
    sys.exit(main())


