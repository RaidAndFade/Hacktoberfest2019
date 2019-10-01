import requests

def execCode(lang,code,instr,auth=""):
    url = "https://api.gocode.it/exec/"+lang
    return requests.request("POST", url, data={"code":code,"input":instr}, headers={"Authorization":auth}).json()
