#!/usr/bin/python2
# -*- coding: utf-8 -*-

import sys
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from gerritlockdb import Projects
from gerritlockdb import Changes
from pygerrit.rest import GerritReview
from requests.exceptions import RequestException
from requests.auth import HTTPDigestAuth
from pygerrit.rest import GerritRestAPI
import ConfigParser
import os
from lockstatus_enum import LockStatusEnum


LOCKSTATUS = LockStatusEnum()


class GerritLock_Client():
    def __init__(self):
        config_parser = ConfigParser.ConfigParser()
        config_parser.read(os.path.join(sys.prefix,
                                        'etc/gerrit-lock/config.ini'))
        username = config_parser.get('default', 'username')
        password = config_parser.get('default', 'password')
        gerrit_url = config_parser.get('default', 'gerrit_url')
        db_url = config_parser.get('default', 'db_url')
        auth = HTTPDigestAuth(username, password)
        self.master_branch = config_parser.get("default", "master_branch").split(",")
        self.rest = GerritRestAPI(url=gerrit_url, auth=auth)
        self.enum = LockStatusEnum()
        
        engine = create_engine(db_url)
        DBsession = sessionmaker(bind=engine)
        self.session = DBsession()

    def lock_all_master_branch(self):
        for branch in self.master_branch:
            projects = self.session.query(Projects).filter(
                Projects.branch_name == branch,
                Projects.lock_status == LOCKSTATUS.UN_LOCK).all()
            for project in projects:
                project.lock_status = LOCKSTATUS.TIME_LOCK
        self.session.commit()
        self.session.close()

    def unlock_all_master_branch(self):
        for branch in self.master_branch:
            projects = self.session.query(Projects).filter(
                Projects.branch_name == branch,
                Projects.lock_status == LOCKSTATUS.TIME_LOCK).all()
            for project in projects:
                project.lock_status = LOCKSTATUS.UN_LOCK
                project.branch_admin = None
                self.handle_change(project)
        self.session.commit()
        self.session.close()

    def add_lock(self, branch_name):
        projects = self.session.query(Projects).filter(
            Projects.branch_name == branch_name,
            Projects.lock_status == LOCKSTATUS.UN_LOCK).all()
        for project in projects:
            project.lock_status = LOCKSTATUS.MANUAL_LOCK
        self.session.commit()
        self.session.close()

    def remove_lock(self, branch_name):
        projects = self.session.query(Projects).filter(
            Projects.branch_name == branch_name).all()
        for project in projects:
            project.lock_status = LOCKSTATUS.UN_LOCK
            self.handle_change(project)
        self.session.commit()
        self.session.close()

    def handle_change(self, project):
        changes = self.session.query(Changes).filter(
            Changes.project_id == project.uid,
            Changes.is_delete == False).all()
        for change in changes:
            change.is_delete = True
            comment = 'recheck'
            print comment, 0, change.change_id, change.patchset
            self.review_comment(comment, 0, change.change_id, change.patchset)
        self.session.commit()

    def review_comment(self, comment, workflow, change_id, patchset):
        review = GerritReview(message=comment, labels={"Workflow": workflow})
        try:
            self.rest.review(change_id, patchset, review)
        except RequestException as errors:
            print errors

    def add_project_admin(self, project_name, admin_str):
        admin_list = admin_str.split(',')
        projects = self.session.query(Projects).filter(
            Projects.project_name == project_name).all()
        self.add_admin(projects, admin_list)

    def remove_project_admin(self, project_name, admin_str):
        admin_list = admin_str.split(',')
        projects = self.session.query(Projects).filter(
                    Projects.project_name == project_name).all()
        self.remove_admin(projects, admin_list)

    def add_branch_admin(self, branch_name, admin_str):
        admin_list = admin_str.split(',')
        projects = self.session.query(Projects).filter(
            Projects.branch_name == branch_name).all()
        self.add_admin(projects, admin_list)

    def remove_branch_admin(self, branch_name, admin_str):
        admin_list = admin_str.split(',')
        projects = self.session.query(Projects).filter(
            Projects.branch_name == branch_name).all()
        self.remove_admin(projects, admin_list)

    def add_admin(self, projects, admin_list):
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
        self.session.commit()

    def remove_admin(self, projects, admin_list):
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
        self.session.commit()

    def pass_change(self, change_id):
        change = self.session.query(Changes).filter(
            Changes.change_id == change_id,
            Changes.is_delete == False).first()
        change.is_delete = True
        comment = 'recheck'
        self.review_comment(comment, 0, change.change_id, change.patchset)
        self.session.commit()
        self.session.close()


def main():
    client = GerritLock_Client()
    if len(sys.argv) < 2:
        client.add_lock("hw/mitaka")
    elif sys.argv[1] == 'addlock':
        client.add_lock(sys.argv[2])
    elif sys.argv[1] == 'unlock':
        client.remove_lock(sys.argv[2])
    elif sys.argv[1] == 'add-project-admin':
        client.add_project_admin(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'add-branch-admin':
        client.add_branch_admin(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'remove-project-admin':
        client.remove_project_admin(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'remove-branch-admin':
        client.remove_branch_admin(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'timelock':
        client.lock_all_master_branch()
    elif sys.argv[1] == 'timeunlock':
        client.unlock_all_master_branch()
    elif sys.argv[1] == 'passchange':
        client.pass_change(sys.argv[2])

if __name__ == '__main__':
    sys.exit(main())

