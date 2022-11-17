import json
import os
import subprocess
from enum import Enum

import yaml

CURR_DIR_PATH = os.path.abspath(os.path.dirname(__file__))
ANSIBLE_MODULES_PATH = os.path.join(CURR_DIR_PATH, "ansible_modules")
ANSIBLE_USER = "giuseppe.daquanno"
                

class AnsibleGatherer:


    class ServerType(Enum):
        WILDFLY = 1
        JBOSS = 2


    def __init__(self, inventory_file_path: str):
        self.inventory_file_path = inventory_file_path

    
    def get_server_names(self):
        server_names = set()
        
        with open(self.inventory_file_path) as inventory_file:
            inventory = yaml.safe_load(inventory_file)

        for server_type in inventory["all"]["children"].keys():
            hosts = inventory["all"]["children"][server_type]["hosts"].keys()
            for host in hosts:
                server_names.add(host)

        return sorted(list(server_names))


    def gather_server_info(self, server_name: str) -> dict:
        server_info = {}
        server_types = self.__get_server_types(server_name)

        ansible_module = "gather_facts"
        ansible_facts = self.__exec_ansible(server_name, ansible_module)["ansible_facts"]
        server_info["system_info"] = self.__fix_ansible_facts(ansible_facts)

        ansible_module = "system_info"
        server_info["system_info"].update(self.__exec_ansible(server_name, ansible_module, True)["system_info"])

        if self.ServerType.WILDFLY in server_types:
            ansible_module = "wildfly_info"
            server_info["wildfly_info"] = self.__exec_ansible(server_name, ansible_module, True)['wildfly_info']

        return server_info

    
    def __fix_ansible_facts(self, ansible_facts: dict) -> dict:
        ret = {}
        
        keys = [
            "ansible_date_time",
            "ansible_distribution", "ansible_distribution_release", "ansible_distribution_version",
            "ansible_architecture", "ansible_processor", "ansible_processor_cores", "ansible_processor_count",
            "ansible_processor_nproc", "ansible_processor_threads_per_core", "ansible_processor_vcpus",
            "ansible_memory_mb",
            "ansible_devices",
            "ansible_all_ipv4_addresses", "ansible_default_ipv4",
            "ansible_all_ipv6_addresses", "ansible_default_ipv6",
            "ansible_dns", "ansible_domain", "ansible_fqdn", "ansible_hostname",
        ]

        interfaces_keys = []
        for interface_name in ansible_facts["ansible_interfaces"]:
            interfaces_keys.append(f"ansible_{interface_name}")

        for key in keys:
            fixed_key = key.replace("ansible_", "")
            ret[fixed_key] = ansible_facts[key]

        ret["mounts"] = {}
        for mount in ansible_facts["ansible_mounts"]:
            mount_point = mount["mount"]
            mount.pop("mount")
            ret["mounts"][mount_point] = mount

        ret["interfaces"] = {}
        for key in interfaces_keys:
            fixed_key = key.replace("ansible_", "")
            ret["interfaces"][fixed_key] = ansible_facts[key]

        return ret


    def __get_server_types(self, server_name: str) -> set:
        server_types = set()

        with open(self.inventory_file_path) as inventory_file:
            inventory = yaml.safe_load(inventory_file)

        for server_type in inventory["all"]["children"].keys():
            hosts = inventory["all"]["children"][server_type]["hosts"].keys()
                
            if server_name in hosts and server_type == "wildfly_servers":
                server_types.add(self.ServerType.WILDFLY)
            elif server_name in hosts and server_type == "jboss_servers":
                server_types.add(self.ServerType.JBOSS)

        return server_types


    def __exec_ansible(self, server_name: str, module_name: str, custom_module_path: bool=False) -> dict:
        cmd = f"ansible -i {self.inventory_file_path} -m {module_name} -u {ANSIBLE_USER} {server_name}"

        if custom_module_path:
            cmd += f" -M {ANSIBLE_MODULES_PATH}"

        ret = subprocess.run(cmd, capture_output=True, shell=True)
        out = ret.stdout.decode("utf-8")
        err = ret.stderr.decode("utf-8")
        err_string = f"\nstdout: {out}\nstderr: {err}"

        if err:
            raise Exception(f"Failed to execute ansible command: {cmd}" + err_string)

        json_start_index = out.find("{")

        try:
            json_data = json.loads(out[json_start_index:])
        except:
            raise Exception(f"Failed to load valid JSON from: \n{out}")

        if "msg" in json_data:
            raise Exception(f"Failed to execute ansible module {module_name}: {json_data['msg']}" + err_string)

        return json_data
