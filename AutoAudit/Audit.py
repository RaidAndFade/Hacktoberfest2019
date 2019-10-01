# Thanks to NCPlayz (https://github.com/NCPlayz) for help creating this script

import os
import requests
from threading import Timer
from unidiff import PatchSet
from datetime import datetime
import gitkey
import gocodeapi
import random
import string

#this should be an env var but i use this script on more than one device so it's just a pain to make it an envvar
API_AUTH = gitkey.GITHUB_AUTH
REPO_URL = "https://api.github.com/repos/RaidAndFade/Hacktoberfest2019/pulls"
RAIDANDFADE_ID = 5139165
HAZARDOUS_TAGS = ("script","style","meta","iframe","img","video","audio","link","svg")
BAD_WORDS = ("anal", "anus", "ballsack", "blowjob", "blow job", "boner", "clit", "cock", "cunt", "dick", "fag", "dildo",
             "fuck", "jizz", "labia", "urethra", "nigg", "penis", "porn", "pussy", "scrotum", "sex", "slut", "smegma",
             "spunk", "twat", "vagina", "wank", "whore")
TOPIC_LABELS = ("week1","week2","week3","week4")
TOPIC_DIRS = ("Yes")
TOPIC_NAMES = ("Just Say Yes")

ISDEBUG = False
TESTPR = None

class PRChecker:
    def __init__(self, pr_info: dict):
        self.pr_info = pr_info

        self._attentions = []
        self._invalids = []

        self.attention_required = False
        self.invalid = False

        #vars to be declared later (this is so that pylint doesnt cry)
        self.number = None
        self.title = None
        self.url = None
        self.author = None
        self.has_contrib_list_submission = False
        self.topic = ""
        self.cannot_mark = False
        self.invalid_reasons = []
        self.attention_reasons = []

        res = self.interpret_pr()

        for attr in res.keys():
            setattr(self, attr, res[attr])

    def add_attention(self, reason: str):
        self._attentions.append(reason)

        if not self.attention_required:
            self.attention_required = True

    def add_invalid(self, reason: str):
        self._invalids.append(reason)

        if not self.invalid:
            self.invalid = True

    def check_yes_submission(self,uname,new_file,fcount):
        self.topic = "week1"
        # self.add_attention("This sort of submission does not have proper checking implemented yet. A maintainer will eventually get to you!")
        if fcount > 1:
            self.add_invalid('More than one file has been added/removed/modified.')
            return

        fpath = new_file['diff'][0].path
        path = os.path.split(fpath)
        if path[1][:12] != "hello_world.":
            self.add_invalid("Your file should be called `hello_world.{ext}` where ext is the language extension. Not "+path[1])
            return
        
        fext = path[1][12:]
        fcontent = new_file['lines'][fpath]

        teststr = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        expectedout = "Enter your name: \nHello "+teststr+"!\n"

        response = gocodeapi.execCode(code=fcontent,lang=fext,instr=teststr,auth=gitkey.GOCODE_AUTH)
        #print(response['data']['res'])
        if response['status']==200:
            if response['data'] and response['data']['res']:
                if expectedout == response['data']['res']:
                    print("Good!")
                else:
                    self.add_invalid("Your submission does not follow the format, Make sure to follow the readme!\n"
                        +"With input `"+teststr+"`:\n"
                        +"You responded with: \n```"
                        +response['data']['res'][:300].strip()+ ("..." if len(response['data']['res'])>300 else "")
                        +"\n```\n while the expected result was: \n```"+expectedout+"\n```")
        else:
            if response['data'] and response['data']['res']:
                self.add_attention("An error occured while marking your code. The error should be addressed by a maintainer eventually. The error is: ```"+response['data']['res']+"```.")
            else:
                self.cannot_mark = True # don't respond if the status != 200 because that means WE fucked up.

        self.add_attention("These submissions must be checked manually because of the potential complexity of submissions, " +
                             "if you've reached this point in the process you're most likely a valid submission.")

    def interpret_pr(self):
        new_file = self.check_diff()

        if new_file is not None:

            fcount = new_file['diff_file'].count("diff --git")

            if fcount < 1:
                self.add_invalid('Less than one file has been added/removed/modified.')
                return

            uname = self.pr_info['user']['login']

            # get the first file (this should be fine)
            path = os.path.split(new_file['diff'][0].path)

            had_contrib_file = False
            for x in new_file['lines']:
                if x == "contributors.md":
                    had_contrib_file = True
                xpath = os.path.split(x)
                firstdir = xpath[0].split("/")[0]
                for ti in range(len(TOPIC_LABELS)):
                    if firstdir == TOPIC_DIRS[ti] and self.topic[-len(TOPIC_LABELS[ti]):] != TOPIC_LABELS[ti]:
                            self.topic += TOPIC_LABELS[ti]

            has_completed_multiple = False
            if self.topic not in TOPIC_LABELS and not had_contrib_file:
                if self.topic!="":
                    has_completed_multiple = True
                    # we should mark this pr as invalid and close it
                    self.topic = ""
                    self.add_invalid("The bot cannot judge multiple submissions in the same Pull Request. Separate your submissions.")

            if had_contrib_file:
                self.add_attention("Modifications to contributors.md must be checked manually, thanks for your submission.")
                fcount-=1
                for xi in range(len(new_file['diff'])):
                    x = new_file['diff'][xi]
                    if x.path == "contributors.md":
                        del new_file['diff'][xi]
                        #self.check_contributors_modification(uname,new_file['lines']['contributors.md'],x)
                del new_file['lines']['contributors.md']
                had_contrib_file = True
                self.has_contrib_list_submission = True
            
            if not has_completed_multiple:
                if path[0] == "Yes":
                    self.check_yes_submission(uname,new_file,fcount)

                elif not had_contrib_file:
                    self.add_invalid('Your file is not in a project folder ("Yes"). This may be intentional, but most likely not. If it is intentional please tag a maintainer.')

        result = {
            'number': self.pr_info['number'],
            'title': self.pr_info['title'],
            'url': self.pr_info['url'],
            'author': self.pr_info['user']['login'],
        }

        if len(self._invalids) > 0:
            result['invalid_reasons'] = self._invalids

        if len(self._attentions) > 0:
            result['attention_reasons'] = self._attentions

        return result

    def check_diff(self):
        diff_file = requests.get(self.pr_info['diff_url'], auth=API_AUTH).text
        if diff_file == "Sorry, this diff is unavailable.":
            self.add_invalid('Your PR looks like an ORPHAN (you deleted the fork). This cannot be automatically checked. Please close this PR and create a new one without removing the fork.')
            return

        diff = PatchSet(diff_file)

        fcount = diff_file.count("diff --git")

        if fcount < 1:
            self.add_invalid('Less than one file has been added/removed/modified.')
            return

        # if any(d.is_modified_file and d.path != "contributors.md" for d in diff):
        #     self.add_attention('This PR modifies one or more pre-existing files.')
        #     return

        new_file = self.parse_diff(diff_file.split("\n"))

        return {'lines': new_file, 'diff': diff, 'diff_file': diff_file}

    def parse_diff(self, diff: list):
        new_file_lines = {}
        current_file = ""
        for line in diff:
            if line.startswith('+') and not line.startswith('+++'):
                new_file_lines[current_file] += f"{line[1:]}\n"
            elif line.startswith('+++'):
                current_file = line[6:]
                new_file_lines[current_file] = ""

       # print(new_file_lines)

        return new_file_lines

def has_label(pr,lblname):
    for lbl in pr['labels']:
        if lbl['name'] == lblname:
            return True
    return False
def do_merge(pr):
    if ISDEBUG: return
    #sha = sha that head must match... i did this manually, but it would have been cool to use the built-in api
    #PUT /repos/:owner/:repo/pulls/:number/merge
    merge_r = requests.put(pr['url']+"/merge",auth=API_AUTH,json={"commit_title":"Auto-Merging PR#"+str(pr['number']),"commit_message":"Automatically merged PR#"+str(pr['number'])+" as it seemed safe."})
    if 'message' in merge_r:
        print(merge_r)
def close(pr):
    if ISDEBUG: return
    #PATCH /repos/:owner/:repo/pulls/:number state=closed
    close_r = requests.patch(pr['url'],auth=API_AUTH,json={"state":"closed"})
    if 'message' in close_r:
        print(close_r)
def add_label(pr,lblname):
    if ISDEBUG: return
    #return
    addl_r = requests.post(pr['issue_url']+"/labels",auth=API_AUTH,json=[lblname]).json()
    if 'message' in addl_r:
        print(addl_r)
def remove_label(pr,lblname):
    if ISDEBUG: return
    #return
    rml_r = requests.delete(pr['issue_url']+"/labels/"+lblname,auth=API_AUTH).json()
    if 'message' in rml_r:
        print(rml_r)
def send_comment(pr,msg):
    if ISDEBUG: return
    msg += "\n\n***This is an automated response, beep boop.\nif you think there is a mistake, contact a maintainer***"
    msg += "\n> "+pr['head']['sha']
    #print(msg)
    #return
    mr = requests.post(pr['comments_url'],auth=API_AUTH,json={'body':msg}).json()
    if 'message' in mr:
        print(mr)

def get_most_recent_bot_comment(pr,cmlist):
    comments = list(cmlist)
    comments.reverse()
    for c in comments:
        if c['user']['id'] == RAIDANDFADE_ID:
            bdy = c['body'].replace("\r","").split('\n')
            if bdy[-1][:2] == "> ":
                return c
    return None

def op_reply_to_latest_bot(pr,cmlist,botcmt):
    found_latest = False
    for c in cmlist:
        if not found_latest:
            if c['id'] == botcmt['id']:
                found_latest = True
            continue
        if c['user']['id'] == pr['user']['id']:
            return c
    return None

def get_bot_checked_sha(c):
    if c is not None:
        bdy = c['body'].replace("\r","").split('\n')
        return bdy[-1][2:]
    return None

def get_labels(pr):
    lbls = []
    for l in pr['labels']:
        lbls = lbls + [l['name']]
    return ",".join(lbls)

def get_cur_time():
    return datetime.time(datetime.now().replace(microsecond=0))

def check_prs():
    print(f"[{get_cur_time()}] ==== Checking PRs ====")
    r = requests.get(REPO_URL, auth=API_AUTH)
    for i in r.json():
        if i['state'] == 'open':
            comment = ""

            if ISDEBUG and TESTPR is not None:
                if TESTPR != i['number']:
                    continue

            print(f"[{get_cur_time()}] "+str(i['number'])+": ",end="")

            if len(i['labels']) > 0:
                prcomments = requests.get(i['comments_url'], auth=API_AUTH).json()
                last_bot_comment = get_most_recent_bot_comment(i,prcomments)
                last_check = get_bot_checked_sha(last_bot_comment)
                if last_bot_comment is not None:
                    msgtime = datetime.strptime(last_bot_comment['created_at'],"%Y-%m-%dT%H:%M:%SZ")
                    curtime = datetime.utcnow()

                if len(prcomments) == 0 or last_bot_comment is None:
                    # Basically, someone else labeled this, or someone deleted the bots' comment. Either way we're out
                    print("<"+get_labels(i)+"> External change to automated flow, skipping.")
                    continue

                # if its been > 24h since issues posted, and needs-work
                if has_label(i,"needs work") and (curtime-msgtime).total_seconds() > 60*60*24: 
                    comment = "This PR has been idle for more than 24 hours, and will now be closed. Feel free to re-open."
                    send_comment(i,comment)
                    close(i)
                    print("<needs work> 24h since issues posted, no response, closing.")
                    continue
                    
                if last_check == i['head']['sha']: # if no new commits were pushed
                    print("<"+get_labels(i)+"> No change since last comment, skipping.")
                    continue

            #these need to be checked/merged by humans, don't bother unless something changes
            if (has_label(i,"attention") or has_label(i,"checked")) and len(prcomments) > 0: 
                if not (last_check == i['head']['sha']):
                    msgtime = datetime.strptime(last_bot_comment['created_at'],"%Y-%m-%dT%H:%M:%SZ")
                    curtime = datetime.utcnow()
                    timediff = (curtime-msgtime).total_seconds()
                    if timediff < 3600: # if its been less than an hour since last comment
                        print("<"+get_labels(i)+"> Changed less than an hour ago, skipping.")
                        continue
                    print("<"+get_labels(i)+"> Changed more than an hour ago: ",end="")
                    comment += "This request's code has changed since approval. Re-Judging contents...\n"
            
            if has_label(i,"needs work") and len(prcomments) > 0:
                # checks if there are new comments BUT the op has not replied since the latest bot comment
                if last_bot_comment['id'] == prcomments[-1]['id'] or (last_bot_comment['id'] != prcomments[-1]['id'] \
                    and op_reply_to_latest_bot(i,prcomments,last_bot_comment) is None):
                    print("<needs work> Changed but no response from OP, skipping.")
                    continue
                
            pr = PRChecker(i)
            if pr.cannot_mark:
                continue
            
            for label in TOPIC_LABELS:
                if pr.topic != label and has_label(i,label):
                    remove_label(i,label)
            
            if pr.topic is not None and pr.topic != "":
                add_label(i,pr.topic)

            if pr.has_contrib_list_submission:
                add_label(i,"contriblist")
            else:
                if has_label(i,"contriblist"):
                    remove_label(i,"contriblist")

            if pr.invalid: # the pr contains a mistake, and is invalid
                reasons = ""
                rc = 1
                for r in pr.invalid_reasons:
                    reasons += f"\n{rc}. {r}"
                    rc += 1 

                print(" invalid because :"+reasons)
                
                comment += "Your pull request needs further work because of the following reason(s):"
                comment += reasons
                comment += "\n\nOnce you have resolved the issues, **comment on this request to be re-judged**"
                if has_label(i,"autochecked"):
                    remove_label(i,"autochecked")
                if has_label(i,"attention"):
                    remove_label(i,"attention")
                send_comment(i,comment)
                if not has_label(i,"needs work"):
                    add_label(i,"needs work")
            elif pr.attention_required: #something is wrong and the pr needs manual approval
                reasons = ""
                rc = 1
                for r in pr.attention_reasons:
                    reasons += f"\n{rc}. {r}"
                    rc += 1 

                print(" needs attention because :"+reasons)
                
                comment += "Your pull request seems good, but must be checked by a human maintainer for the following reason(s):"
                comment += reasons
                comment += "\n\nPlease be patient until a maintainer has time to look over your contribution."
                if has_label(i,"autochecked"):
                    remove_label(i,"autochecked")
                if has_label(i,"needs work"):
                    remove_label(i,"needs work")
                send_comment(i,comment)
                if not has_label(i,"attention"):
                    add_label(i,"attention")
            else: # the pr looks good and can be merged by me
                if has_label(i,"needs work"):
                    remove_label(i,"needs work")
                if has_label(i,"attention"):
                    remove_label(i,"attention")
                if not has_label(i,"autochecked"):
                    add_label(i,"autochecked")

                print(" clean, being merged now. ",end="")
        
                comment += "Your pull request looks good, and is ready for merging!"
                comment += "\n\nThank you for being a part of Open Source, I hope you continue to help other repositories in the future!"
                send_comment(i,comment)
                do_merge(i)
            print("",flush=True)
    print(f"[{get_cur_time()}] ==== Finished ===")

if __name__ == '__main__':
    check_prs()
    while not ISDEBUG:
        t = Timer(900, check_prs) # check every 900s (15m)
        t.start()
        t.join()
