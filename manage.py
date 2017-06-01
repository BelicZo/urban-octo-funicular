#!/usr/bin/python2
# -*- coding: utf-8 -*-
import os
import sys
import yaml
import uuid
from pygerrit.error import GerritError
from gerritlockdb import Projects


PROJECT_LIST_URL = "/projects/?d"
BRANCH_LIST_URL = "/projects/%s/branches/"


class Manager(object):
    def load_projects(self, rest, session,branch_list):
        try:
            ses = session()
            projects_info = rest.get(PROJECT_LIST_URL)
            projects_list = self.load_projects_list()
            for project_name in projects_info:
                if project_name in projects_list:
                    branches_url = BRANCH_LIST_URL % projects_info[project_name]['id']
                    branches = rest.get(branches_url)
                    for branch_info in branches:
                        ref = branch_info['ref'].split('/')
                        if ref[0] == 'HEAD':
                            continue
                        if len(ref) == 4:
                            branch_name = ref[2] + "/" + ref[3]
                        else:
                            branch_name = ref[2]
                        pj = ses.query(Projects).filter(
                            Projects.project_name == project_name,
                            Projects.branch_name == branch_name).first()
                        if pj:
                            continue
                        else:
                            if branch_name in branch_list:
                                new_pj = Projects(uid=str(uuid.uuid4()),
                                                  project_name=project_name,
                                                  branch_name=branch_name)
                                ses.add(new_pj)
                                ses.commit()
            ses.close()
        except GerritError as errors:
            raise errors

    def load_projects_list(self):
        path = os.path.join(sys.prefix,
                            'etc/gerrit-lock/file_list.txt')
        with open(path, "r") as stream:
            try:
                projects_list = []
                for i in stream.readlines():
                    projects_list.append(str(i[:-1]))
                return projects_list
            except Exception as errors:
                raise errors

    def load_users(self):
        path = os.path.join(sys.prefix,
                            'etc/gerrit-lock/special_users.yaml')
        with open(path, "r") as stream:
            try:
                special_users = yaml.load(stream)
                return special_users
            except yaml.YAMLError as errors:
                raise errors

