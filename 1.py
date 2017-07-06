class CCM(object):

    def __init__(self, event, rest, session):
        self.event = event
        self.rest = rest
        self.session = session
        self.check_api = 'http://alm-uat.huawei.com/interface/services/common/query'
        self.commit_api = 'http://alm-uat.huawei.com/code/services/rest/code/commit/save'
        self.headers = {"username": 'devsync_alm_user',
                        "password": 'devsync_alm_pwd',
                        "Context-type": "application/json;charset=UTF-8"}
        self.req_num = list()
        self.dts_num = list()
        self.comment_postfix = "\n\n\n" \
                          "REF: http://3ms.huawei.com/hi/group/1005027/wiki_4791219.html"

    def extract_message(self):
        check_status = self.check_status()
        if check_status and check_status > 0:
            comment = "Error (Jarvis Bot): "
            mes = self.event.json['change']['commitMessage']
            req_l = re.findall(r'ar.*?\w+|req.*?\w+|story.*?\w+', mes, re.I)

            bug_l = re.findall(r'bug.*?[a-zA-Z0-9]+', mes, re.I)
            bug_id = ','.join(bug_l)
            if len(req_l) != 0:
                req_id = ','.join(req_l)
                if u'：' in req_id or u'：' in bug_id:
                    print "此时ID编号中不该出现中文冒号"
                    comment += "此时ID编号中不该出现中文冒号"
                    comment += self.comment_postfix
                elif ': ' not in req_id or ': ' not in bug_id:
                    print "ID编号中冒号后面应该有空格的"
                    comment += "ID编号中冒号后面应该有空格的"
                    comment += self.comment_postfix
                else:
                    print "验证通过"
                    req_num = re.findall(r'(?<=AR: )\w+|(?<=req: )\w+|(?<=story: )\w+', req_id, re.I)
                    dts_num = re.findall(r'(?<=BUG: )\w+', bug_id, re.I)
                    self.check_require(','.join(req_num))
                    if len(bug_l) != 0:
                        self.check_bug(','.join(dts_num))
                        self.commit_message()
                    return
            else:
                print "CommitMessage必须提供需求有效性验证码"
                comment += "CommitMessage必须提供需求有效性验证码"
                comment += self.comment_postfix
            if check_status == 2:
                self.review_comment(comment, self.rest, -2, self.event.change.number, self.event.patchset.revision)
            else:
                self.review_comment(comment, self.rest, 0, self.event.change.number, self.event.patchset.revision)

        else:
            print "此事件不在列表中或在列表中但不需要检查"
            return

    def check_require(self, req_id):
        data = {
                "where": {"type": "requirement", "requirement_number": req_id, },
                "fields": "id,state,requirement_number",
                "pageSize": "100",
                "pageNo": "1"
                }
        response = requests.post(url=self.check_api, json=data, headers=self.headers)
        print response.text
        res_data = json.loads(response.text)
        if res_data["result"]["amount"] > 0:
            for i in range(res_data["result"]["amount"]):
                self.req_num.append(res_data["data"][i]["requirement_number"])
        else:
            print "需求有效性检查失败"
        return response.text

    def check_bug(self, bug_id):
        data = {
            "where": {"type": "defect", "defect_number": bug_id, },
            "fields": "id,state,defect_number",
            "pageSize": "100",
            "pageNo": "1"
        }
        response = requests.post(url=self.check_api, json=data, headers=self.headers)
        print response.text
        res_data = json.loads(response.text)
        if res_data["result"]["amount"] > 0:
            for i in range(res_data["result"]["amount"]):
                self.dts_num.append(res_data["data"][i]["defect_number"])
        else:
            print "缺陷有效性检查失败"
        return response.text

    def commit_message(self):
        change_id = self.event.change.change_id
        project_name = self.event.change.project
        branch = self.event.change.branch
        revision = self.event.patchset.revision
        mr_url = self.event.change.url
        server_url = '/'.join(mr_url.split('/')[:3])+'/'+self.event.change.project
        author = self.event.json['author']['username']
        subject = self.event.change.subject
        commit_date = time.strftime("%Y-%m-%d %X", time.localtime(self.event.json["patchSet"]["createdOn"]))
        merge_date = time.strftime("%Y-%m-%d %X", time.localtime(self.event.json["eventCreatedOn"]))
        res = self.rest.get("/changes/?q=%s&o=CURRENT_REVISION"
                       "&o=CURRENT_COMMIT&o=CURRENT_FILES&o=DOWNLOAD_COMMANDS" \
                       % (change_id))
        files = res[0]['revisions'][revision]['files']
        file_list = self.format_file_list(files)
        data = {
            "dts_num": self.dts_num,
            " requirement_number": self.req_num,
            "commit_tool": "Gerrit",
            "change_id": change_id,
            "ci_project_name": project_name,
            "branch": branch,
            "scm_type": "GIT",
            "server_url": server_url,
            "mr_url": mr_url,
            "revision": revision,
            "author": author,
            "comment": subject,
            "commit_date": commit_date,
            "merge_date": merge_date,
            "file_list": file_list
        }
        response = requests.post(url=self.commit_api, json=data, headers=self.headers)
        print response.text
        if json.loads(response.text)["status"] == "success":
            print("提交成功")
        else:
            print("提交失败")

    def review_comment(self, comment, rest, cr, change_id, patchset):
        review = GerritReview(message=comment, labels={"Code-Review": cr})
        try:
            rest.review(change_id, patchset, review)
        except RequestException as errors:
            logging.error("Error: %s", errors)

    def format_file_list(self, files):
        file_list = list()
        for i, j in files.iteritems():
            c = dict()
            c["file_path"] = i
            if j.has_key('status'):
                if j['status'] == 'A':
                    c["operation"] = "Add"
                    c["lines_inserted"] = str(j["lines_inserted"])
                    c["lines_deleted"] = "0"
                elif j['status'] == 'D':
                    c["operation"] = "Delete"
                    c["lines_deleted"] = str(j["lines_deleted"])
                    c["lines_inserted"] = "0"
            else:
                c["operation"] = "Modify"
                c["lines_inserted"] = str(j["lines_inserted"])
                c["lines_deleted"] = str(j["lines_deleted"])
            file_list.append(c)
        return file_list

    def check_status(self):
        session = self.session()
        c = session.query(Check).filter(
            Check.project_name == self.event.change.project,
            Check.branch_name == self.event.change.branch
        ).first()
        if c:
            return c.is_check
        else:
            return None
        
        
        
        
        
        
        
        
        
        
        
        
        
        
