#!/usr/bin/python

# Copyright: (c) 2022, Giuseppe D" Aquanno <GiuDaquan@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: system_info

short_description: The module gathers information about WildFly server instances.

# If this is part of a collection, you need to use semantic versioning,
# i.e. the version is of the form "2.5.0" and not "2.4".
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

# Specify this value according to your collection
# in format of namespace.collection.doc_fragment_name
extends_documentation_fragment:
    - my_namespace.my_collection.my_doc_fragment_name

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
# These are examples of possible return values, and in general should use other names for return values.
original_message:
    description: The original name param that was passed in.
    type: str
    returned: always
    sample: "hello world"
message:
    description: The output message that the test module generates.
    type: str
    returned: always
    sample: "goodbye"
"""

import glob
import os
import re
import subprocess
import xml.etree.ElementTree as ET
import shutil
from asyncio.subprocess import PIPE

from ansible.module_utils.basic import AnsibleModule


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
    #    name=dict(type="str", required=True),
    #    new=dict(type="bool", required=False, default=False)
    )

    result = dict(changed=False, system_info={})

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    if module.check_mode:
        module.exit_json(**result)

    system_info = result["system_info"]
    system_info["errors"] = []

    # get general system information
    try:
        system_info["selinux_status"] = get_selinux_info()
    except Exception as e:
        system_info["selinux_status"] = None
        system_info["errors"].append(str(e))
    
    try:
        system_info["nagios_status"] = get_nagios_info()
    except Exception as e:
        system_info["nagios_status"] = None
        system_info["errors"].append(str(e))

    try:
        system_info["logrotate_conf"] = get_logrotate_info()
    except Exception as e:
        system_info["logrotate_conf"] = None
        system_info["errors"].append(str(e))

    try:
        system_info["packages"] = get_pkg_list()
    except Exception as e:
        system_info["packages"] = None
        system_info["errors"].append(str(e))
        
   
    module.exit_json(**result)


def main():
    run_module()


def get_selinux_info():
    sestatus_cmd = "sestatus"
    sestatus_out = subprocess.run(sestatus_cmd, stdout=PIPE, shell=True).stdout.decode("utf-8", errors="replace")
    
    if "SELinux status" not in sestatus_out:
        raise Exception("Failed to read Selinux Status")
    
    sestatus_out = sestatus_out.replace("SELinux status:", "").strip()

    return sestatus_out


def get_iptables_info():
    iptables_cmd = []


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


def get_nagios_info():
    chkconfig_cmd = "chkconfig nrpe"
    chkconfig_out = subprocess.run(chkconfig_cmd, stdout=PIPE, shell=True).stdout.decode("utf-8", errors="replace").strip()

    if chkconfig_out != "enabled" and chkconfig_out != "disabled":
        raise Exception("Failed to read Nagios Status")

    return chkconfig_out


def get_pkg_list():
    ret = {}
    yum_cmd = "yum list installed"
    yum_out = subprocess.run(yum_cmd, stdout=subprocess.PIPE, shell=True).stdout.decode("utf-8", errors="replace")

    if "Installed Packages" not in yum_out:
        raise Exception("Failed to read yum package list")

    for line in yum_out.splitlines()[2:]:
        pkg_name, pkg_version, pkg_owner = [word for word in line.split(" ") if word]
        ret[pkg_name] = {}
        ret[pkg_name]["version"] = pkg_version
        ret[pkg_name]["owner"] = pkg_owner

    return ret if ret else None


if __name__ == "__main__":
    main()
