import json
import src.server_sniffer_utils.ansible_gatherer as ans_gat
import re
import xml.etree.ElementTree as ET
import os
import subprocess
from subprocess import PIPE

def get_logrotate_info():
    ret = {}
    logrotate_conf_dir = "/etc/logrotate.d"
    
    if not os.path.isdir(logrotate_conf_dir):
        raise Exception("Failed to read Logrotate Status")

    conf_regex = re.compile(r"({(.+)})", re.DOTALL)

    for file in os.listdir(logrotate_conf_dir):
        cat_cmd = f"cat {os.path.join(logrotate_conf_dir, file)}"
        cat_out = subprocess.run(cat_cmd, stdout=PIPE, shell=True).stdout.decode("utf-8", errors="replace")

        conf = conf_regex.search(cat_out)
        conf_blob = conf.group(1)

        file_lines = cat_out.replace(conf_blob, "").splitlines()
        file_lines = [line.strip() for line in file_lines if line and "#" not in line]

        conf_lines = conf.group(2).splitlines()
        conf_lines = [line.strip() for line in conf_lines if line]

        ret[file] = {}
        ret[file]["log_files"] = file_lines
        ret[file]["conf"] = conf_lines

    return ret

get_logrotate_info()


ansible_gatherer = ans_gat.AnsibleGatherer('/home/giuseppe-daquanno/Desktop/inventory.yaml')
servers = ansible_gatherer.get_server_names()
server_info = ansible_gatherer.gather_server_info(servers[0])

with open(f'{servers[0]}_info.json', 'w+') as server_info_file:
    print(json.dumps(server_info, indent=4))
    json.dump(server_info, server_info_file)