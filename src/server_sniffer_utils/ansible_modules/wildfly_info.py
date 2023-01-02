#!/usr/bin/python

# Copyright: (c) 2022, Giuseppe D" Aquanno <GiuDaquan@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: wildfly_info

short_description: The module gathers information about WildFly application servers.

version_added: "1.0.0"

description: This is my longer description explaining my test module.

options:
    name:
        description: This is the message to send to the test module.
        required: true
        type: str
    new:
        description:
            - Control to demo if the result of this module is changed or not.
            - Parameter description can be a list as well.
        required: false
        type: bool

author:
    - Giuseppe D"Aquanno (@GiuDaquan)
"""

EXAMPLES = r"""
# Pass in a message
- name: Test with a message
  my_namespace.my_collection.my_test:
    name: hello world

# pass in a message and have changed true
- name: Test with a message and changed output
  my_namespace.my_collection.my_test:
    name: hello world
    new: true

# fail the module
- name: Test failure of the module
  my_namespace.my_collection.my_test:
    name: fail me
"""

RETURN = r"""
# These are examples of possible return values.
wildfly_info:
    description: Reports the application server configuration.
    type: dict
    returned: always
    sample: {
        "wildfly_info": {
            "service_conf": {
                "environment": "LAUNCH_JBOSS_IN_BACKGROUND=1",
                "environment_file": "/etc/wildfly/wildfly.conf",
                "exec_start": "/usr/local/wildfly-26.1.0.Final/bin/launch.sh $WILDFLY_MODE $WILDFLY_CONFIG $WILDFLY_BIND",
                "limit_nofile": "102642",
                "pid_file": "/var/run/wildfly/wildfly.pid",
                "stdout": "null",
                "user": "jboss   "
            },
            ...
        }
    }
"""

import glob
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from asyncio.subprocess import PIPE
from typing import Callable, Dict, List, Pattern, Tuple, Union
from xml.etree.ElementTree import Element

from ansible.module_utils.basic import AnsibleModule

SERVICE_CONF_DIR = "/etc/systemd/system/"
WILDFLY_CONF_PATH = "/usr/local/wildfly/standalone/configuration/standalone.xml"
WILDFLY_CONTENT_PATH = "/usr/local/wildfly/standalone/data/content"
LOCAL_DIR = "/usr/local"
WORK_DIR = "/tmp/server_sniffer/"
ORG_DIR = "/homes/36346daquanno/org"


def run_module() -> None:
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
    #    name=dict(type="str", requirefd=True),
    #    new=dict(type="bool", required=False, default=False)
    )

    result = dict(changed=False, wildfly_info={})

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    if module.check_mode:
        module.exit_json(**result)

    total, used, free = shutil.disk_usage("/")
    if used / total > 0.9:
        module.fail_json(msg="Low storage space detected", **result)

    wildfly_info = result["wildfly_info"]
    wildfly_info["errors"] = []

    env_file_path = None
        
    # read wildfly service configuration file
    try:
        wildfly_info["service_conf"] = get_service_conf_info()
        env_file_path = wildfly_info["service_conf"]["environment_file"]
    except Exception as e:
        wildfly_info["service_conf"] = None
        wildfly_info["errors"].append(f"service_conf: {str(e)}")

    # read wildfly environment file
    try:
        wildfly_info["env_file"] = get_environment_file_info(env_file_path)
    except Exception as e:
        wildfly_info["env_file"] = None
        wildfly_info["errors"].append(f"env_file: {str(e)}")

    # read org file
    try:
        wildfly_info["org"] = get_org_info()
    except Exception as e:
        wildfly_info["errors"].append(f"org: {str(e)}")

    # get wildfly_version
    version_regex = re.compile(r"wildfly-([0-9]+.[0-9]+.[0-9]+)")
    subdirs = " ".join(os.listdir(LOCAL_DIR))
    wildfly_info["version"] = version_regex.search(subdirs).group(1)

    # read wildfly configuration file
    cat_cmd = f"cat {WILDFLY_CONF_PATH}"
    cat_out = subprocess.run(cat_cmd, stdout=PIPE, shell=True).stdout.decode("utf-8", errors="replace")

    wildfly_info["users"] = get_users_info(cat_out)
    wildfly_info["datasources"] = get_datasources_info(cat_out)
    wildfly_info["log_files"] = get_logs_info(cat_out)
    wildfly_info["deployments"] = get_deployments_info(cat_out, WILDFLY_CONTENT_PATH)

    module.exit_json(**result)


def main():
    run_module()


# ----------------------------------------------------------------------------------------------------------------------
# Wildfly configuration files dicovery
# ----------------------------------------------------------------------------------------------------------------------
def get_service_conf_info() -> Dict:
    if len(glob.glob(SERVICE_CONF_DIR + "wildfly*.service")) != 1:
        raise Exception(f"No configuration file at {SERVICE_CONF_DIR}")

    ret = {}
    cat_cmd = f"cat {SERVICE_CONF_DIR}" + "wildfly*.service"    
    cat_out = subprocess.run(cat_cmd, stdout=PIPE, shell=True).stdout.decode("utf-8", errors="replace")
    
    try:
        ret["environment"] = re.search(r"Environment=(.*)", cat_out).group(1)
        # Da risolvere la questione del trattino
        ret["environment_file"] = re.search(r"EnvironmentFile=-(.*)", cat_out).group(1)
        ret["user"] = re.search(r"User=(.*)", cat_out).group(1)
        ret["limit_nofile"] = re.search(r"LimitNOFILE=(.*)", cat_out).group(1)
        ret["pid_file"] = re.search(r"PIDFile=(.*)", cat_out).group(1)
        ret["exec_start"] = re.search(r"ExecStart=(.*)", cat_out).group(1)
        ret["stdout"] = re.search(r"StandardOutput=(.*)", cat_out).group(1)
    except:
        raise Exception(f"Failed to read service configuration file at {SERVICE_CONF_DIR}")

    return ret


def get_environment_file_info(env_file_path: str) -> Dict:
    if not os.path.isfile(env_file_path):
        raise Exception(f"No environment configuration file at {env_file_path}")

    ret = {}
    cat_cmd = f"cat {env_file_path}"
    cat_out = subprocess.run(cat_cmd, stdout=PIPE, shell=True).stdout.decode("utf-8", errors="replace")
    
    try:
        ret["config"] = re.search(r"WILDFLY_CONFIG=(.*)", cat_out).group(1)
        ret["mode"] = re.search(r"WILDFLY_MODE=(.*)", cat_out).group(1)
        ret["bind"] = re.search(r"WILDFLY_BIND=(.*)", cat_out).group(1)
    except:
        raise Exception(f"Failed to read environment configuration file at{env_file_path}")

    return ret
#/----------------------------------------------------------------------------------------------------------------------
# Wildfly configuration files dicovery
#/----------------------------------------------------------------------------------------------------------------------


#/----------------------------------------------------------------------------------------------------------------------
# Wildfly configuration file data extraction
#/----------------------------------------------------------------------------------------------------------------------
def get_users_info(wildfly_conf_file: str) -> Dict:
    ret = {}

    root = ET.fromstring(wildfly_conf_file)
    ns_list = find_ns(root)
    root_ns = ns_list[0]
    xpath = f"./{root_ns}management/{root_ns}access-control/{root_ns}role-mapping/{root_ns}role"
    roles = root.findall(xpath)

    for role in roles:
        role_name = role.get("name")
        ret[role_name] = {}
        ret[role_name]["users"] = []
        ret[role_name]["groups"] = []
                
        for elem in role.find(f"{root_ns}include"):
            if f"{root_ns}user" == elem.tag:
                ret[role_name]["users"].append(elem.get("name"))
            elif f"{root_ns}group" == elem.tag:
                ret[role_name]["groups"].append(elem.get("name"))

    return ret


def get_datasources_info(wildfly_conf_file: str) -> Dict:
    ret = {}
    
    root = ET.fromstring(wildfly_conf_file)
    ns_list = find_ns(root, ["profile", "subsystem"], ["", "datasources"])
    root_ns = ns_list[0]
    ds_ns = ns_list[1]
    xpath = f"./{root_ns}profile/{ds_ns}subsystem/{ds_ns}datasources/{ds_ns}datasource"
    datasources = root.findall(xpath)

    for datasource in datasources:
        jndi_name = datasource.get("jndi-name")
        ret[jndi_name] = {}
        ret[jndi_name]["pool_name"] = datasource.get("pool-name")
        ret[jndi_name]["connection_url"] = datasource.findtext(f"{ds_ns}connection-url")
        ret[jndi_name]["driver"] = datasource.findtext(f"{ds_ns}driver")

        security = datasource.find(f"{ds_ns}security")
        ret[jndi_name]["username"] = security.findtext(f"{ds_ns}user-name") if security else None
    
    return ret


def get_logs_info(wildfly_conf_file: str) -> Dict:
    ret = {}

    root = ET.fromstring(wildfly_conf_file)
    ns_list = find_ns(root, ["profile", "subsystem"], ["", "logging"])
    root_ns = ns_list[0]
    log_ns = ns_list[1]
    xpath = f"./{root_ns}profile/{log_ns}subsystem"
    handlers = root.find(xpath).findall("./")
    
    for handler in handlers:
        file = handler.find(f"{log_ns}file")
        if file is not None:
            file_name = file.get("path")
            ret[file_name] = {}
            ret[file_name]["path"] = file.get("relative-to")

            rotation = handler.find(f"{log_ns}rotate-size")
            ret[file_name]["rotation"] = rotation.get("value") if rotation is not None else None

    return ret


def get_deployments_info(wildfly_conf_file: str, wildfly_content_path: str) -> Dict:
    ret = {}
    hashes = {}

    root = ET.fromstring(wildfly_conf_file)
    ns_list = find_ns(root)
    root_ns = ns_list[0]
    xpath = f"./{root_ns}deployments/{root_ns}deployment"
    deployments = root.findall(xpath)

    for deployment in deployments:
        deployment_hash = deployment.find(f"{root_ns}content").get("sha1")
        
        hashes[deployment_hash] = {}
        hashes[deployment_hash]["deployment_name"] = deployment.get("name")
        hashes[deployment_hash]["runtime_name"] = deployment.get("runtime-name")

    for hash_prefix in os.listdir(wildfly_content_path):
        for hash_remainder in os.listdir(os.path.join(wildfly_content_path, hash_prefix)):
            dep_file_name = os.listdir(os.path.join(wildfly_content_path, hash_prefix, hash_remainder))[0]
            dep_file_path = os.path.join(wildfly_content_path, hash_prefix, hash_remainder, dep_file_name)

            assembled_hash = hash_prefix + hash_remainder
            deployment_name = hashes[assembled_hash]["deployment_name"]
            runtime_name = hashes[assembled_hash]["runtime_name"]
            deployment_entry = extract_deployment_data(dep_file_path, runtime_name, assembled_hash)

            ret[deployment_name] = deployment_entry
    
    return ret
#/----------------------------------------------------------------------------------------------------------------------
# Wildfly configuration file data extraction
#/----------------------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
# Wildlfy deployment data extraction
# ----------------------------------------------------------------------------------------------------------------------
def extract_deployment_data(ear_file_path: str, runtime_name: str, deployment_hash: str) -> Dict:
    ret = {}

    if os.path.exists(WORK_DIR):
        shutil.rmtree(WORK_DIR)
    os.makedirs(WORK_DIR)

    with zipfile.ZipFile(ear_file_path) as archive_file:
        archive_file.extractall(WORK_DIR)
    
    archives_extensions = ["war", "jar"]
    extract_archives(archives_extensions)

    pool_extensions = ["xml", "properties"]
    file_pool = generate_file_pool(pool_extensions)

    ctx_root_regex = re.compile(r"<context-root>(.+)</context-root>")
    datasource_regex = re.compile(r"dsName=(java:/?[A-Za-z0-9]+/[A-Za-z0-9]+/[A-Za-z0-9]+)")
    ret["context_root"] = search_pool(file_pool, ctx_root_regex)
    ret["datasources"] = search_pool(file_pool, datasource_regex)

    ret["dependencies"] = read_archive_file("jboss-deployment-structure.xml", get_deployment_structure_info)
    ret["log_file"] = read_archive_file("log4j.xml", get_deployemnt_log_file_info)
    ret["roles"] = read_archive_file("web.xml", get_deployment_roles_info)

    ret["runtime_name"] = runtime_name
    ret["sha1"] = deployment_hash

    return ret


def get_deployment_structure_info(raw_file: str) -> Dict:
    ret = {}

    root = ET.fromstring(raw_file)
    xpath = f"./deployment/dependencies/module"
    modules = root.findall(xpath)

    ret["self"] = [module.get("name") for module in modules]

    xpath = f"./sub-deployment"
    submodules = root.findall(xpath)

    for submodule in submodules:
        module_name = submodule.get("name")
        modules = submodule.findall("./dependencies/module")
        ret[module_name]= [module.get("name") for module in modules]

    return ret


def get_deployemnt_log_file_info(raw_file: str) -> Dict:
    ret = {}

    root = ET.fromstring(raw_file)
    xpath = f"./appender"
    appender = root.find(xpath)

    file_name_regex = re.compile(r"\$\{(.+)\}\/(.+)")

    for param in appender.findall("./"):
        if param.get("name") == "File":
            match = file_name_regex.search(param.get("value"))
            file_name = match.group(2)
            path = match.group(1)
            ret["name"] = file_name
            ret["path"] = path

        if param.get("name") == "MaxFileSize":
            ret["rotation"] = param.get("value")

    return ret


def get_deployment_roles_info(raw_file: str) -> List[str]:
    root = ET.fromstring(raw_file)
    xpath = f"./security-role"
    roles = root.findall(xpath)

    return [role.findtext("role-name").strip() for role in roles]
#/----------------------------------------------------------------------------------------------------------------------
# Wildfly deployment data extraction
#/----------------------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
# Organization data extraction
# ----------------------------------------------------------------------------------------------------------------------
def get_org_info() -> Dict:
    ret = {}
    files = os.listdir(ORG_DIR)
    
    if not files:
        raise Exception(f"Failed to read org file at {ORG_DIR}")

    for file in files:
        file_name = re.search(r"(.*)\.", file).group(1)
        cat_cmd = f"cat {os.path.join(ORG_DIR, file)}"
        cat_out = subprocess.run(cat_cmd, stdout=PIPE, shell=True).stdout.decode("utf-8", errors="replace").split("\n")
        ret[file_name] = [line for line in cat_out if line]

    return ret

#/----------------------------------------------------------------------------------------------------------------------
# Organization data extraction
#/----------------------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
# XML Helpers
# ----------------------------------------------------------------------------------------------------------------------
def find_ns(xml_root: Element, tag_list: List[str]=[], ns_keywords: List[str]=[]) -> str:
    ret_ns = []
    ns_regex = re.compile(r"(\{.*\})(.*)")
    match = ns_regex.search(xml_root.tag)
    ret_ns.append(match.group(1))

    while len(tag_list) > 0 and len(ns_keywords) > 0:
        search_tag = tag_list.pop(0)
        ns_keyword = ns_keywords.pop(0)
        children = xml_root.findall("./")
        
        xml_root, found_ns = find_match(children, search_tag, ns_keyword, ns_regex)
        ret_ns = ret_ns + [found_ns] if found_ns not in ret_ns else ret_ns

    return ret_ns


def find_match(xml_elems: List[Element], search_tag: str, ns_keyword: str, regex: Pattern) -> Tuple[Element, str]:
    for elem in xml_elems:
        match = regex.search(elem.tag)
        ns = match.group(1)
        tag = match.group(2)

        if ns_keyword in ns and tag == search_tag:
            return elem, ns
#/---------------------------------------------------------------------------------------------------------------------
# XML Helpers
#/----------------------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
# Archives Helpers
# ----------------------------------------------------------------------------------------------------------------------
def extract_archives(archive_extensions: List[str]) -> None:
    for ext in archive_extensions:
        find_cmd = f"find {WORK_DIR} -name *.{ext}"
        archives = subprocess.run(find_cmd, stdout=PIPE, shell=True).stdout.decode("utf-8", errors="replace").split("\n")
        archives.remove("")

        for archive in archives:
            sub_dir_name = os.path.join(WORK_DIR, archive.split("/")[-1].replace(f".{ext}", "")) + f"_{ext}"
            
            if not os.path.exists(sub_dir_name):
                os.makedirs(sub_dir_name)

            with zipfile.ZipFile(archive) as archive_file:
                archive_file.extractall(sub_dir_name)

    return


def read_archive_file(file_name: str, handler: Callable[[str], dict]) -> Union[Dict, None]:
    find_cmd = f"find {WORK_DIR} -name {file_name}"
    file_path = subprocess.run(find_cmd, stdout=PIPE, shell=True).stdout.decode("utf-8", errors="replace").strip()

    if not file_path:
        return None

    cat_cmd = f"cat {file_path}"
    cat_out = subprocess.run(cat_cmd, stdout=PIPE, shell=True).stdout.decode("utf-8", errors="replace")
    
    return handler(cat_out) if cat_out else None
#/----------------------------------------------------------------------------------------------------------------------
# Archives Helpers
#/----------------------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
# File Pool Helpers
# ----------------------------------------------------------------------------------------------------------------------
def generate_file_pool(pool_extensions: List[str]) -> List[str]:
    ret = []

    for ext in pool_extensions:
        find_cmd = f"find {WORK_DIR} -name *.{ext}"
        files = subprocess.run(find_cmd, stdout=PIPE, shell=True).stdout.decode("utf-8", errors="replace").split("\n")
        files.remove("")
        ret += files

    return ret


def search_pool(file_pool: List[str], regex: Pattern) -> Union[List[str], str, None]:
    ret = set()

    for file in file_pool:
        cat_cmd = f"cat {file}"
        cat_out = subprocess.run(cat_cmd, stdout=PIPE, shell=True).stdout.decode("utf-8", errors="replace")
        match = regex.search(cat_out)
        ret = ret | {match.group(1)} if match else ret

    if len(ret) > 1:
        ret = list(ret)
    elif len(ret) == 1:
        ret = ret.pop()
    else:
        ret = None

    return ret
#/----------------------------------------------------------------------------------------------------------------------
# File Pool Helpers
#/----------------------------------------------------------------------------------------------------------------------


if __name__ == "__main__":
    main()
