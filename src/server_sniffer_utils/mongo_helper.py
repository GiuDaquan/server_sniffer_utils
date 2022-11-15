import datetime
import re

from deepdiff import DeepDiff
from pymongo import MongoClient
from pymongo.collection import Collection
from datetime import datetime


class MongoHelper:


    def __init__(self, db_name: str, host:str, port: str, username: str="", password: str=""):
        self.client = MongoClient(host=host, port=int(port), username=username, password=password)
        self.db_handle = self.client[db_name]

    
    def get_collection(self, collection: str) -> Collection:
        return self.db_handle[collection]


    def find_document(self, collection: str, server_name: str):
        db = self.db_handle[collection]
        db.find_one({'system_info.hostname': server_name.lower()}, projection={'_id': False})


    def get_ddiff(self, document_x: dict, document_y: dict) -> dict:
        ret = {}

        ddiff = DeepDiff(document_x, document_y)

        ret["items_changed"] = self.__get_dict(ddiff, "values_changed", ddiff.t2)
        ret["items_added"] = self.__get_dict(ddiff, "dictionary_item_added", ddiff.t2)
        ret["items_removed"] = self.__get_dict(ddiff, "dictionary_item_removed", ddiff.t1)

        return ret


    def __apply_projection(self, server_info: dict) -> None:
        system_info = server_info["system_info"]
        wildfly_info = server_info["wildfly_info"]

        system_info.pop("date_time", None)
        system_info.pop("errors", None)

        wildfly_info.pop("errors", None)

        return


    def extract_timestamps(self, server_info: dict) -> datetime:
        date = server_info["system_info"]["date_time"]["date"]
        year, month, day = [int(elem) for elem in date.split("-")]
        time = server_info["system_info"]["date_time"]["time"]
        hour, minute, second = [int(elem) for elem in time.split(":")]
        return datetime(year, month, day, hour, minute, second)

    
    def __get_dict(self, ddiff: DeepDiff, entry_key: str, value_src: dict):
        ret = {}

        for key in ddiff[entry_key]:
            subkeys = key.replace("root", "").split("[")
            subkeys = [subkey.replace("\'", "").replace("]", "") for subkey in subkeys if subkey]

            entry = ret
            value = value_src
            for idx, subkey in enumerate(subkeys):
                value = value[subkey]
                entry[subkey] = entry.setdefault(subkey, {}) if idx < len(subkeys) - 1 else value
                entry = entry[subkey]
        

        return ret