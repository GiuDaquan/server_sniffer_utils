import datetime
import re
from typing import List, Tuple

from deepdiff import DeepDiff
from pymongo import MongoClient


class MongoHelper:


    def __init__(self, db_name: str, host:str, port: str, username: str="", password: str=""):
        self.client = MongoClient(host=host, port=int(port), username=username, password=password)
        self.db_handle = self.client[db_name]
        self.DATE_FORMAT = "%Y-%m-%d"

    
    def get_collection_name(self, date: datetime.datetime) -> str:
        return date.strftime(self.DATE_FORMAT)


    def get_collection_date(self, date: str) -> datetime.date:
        return datetime.datetime.strptime(date, self.DATE_FORMAT).date()

    
    def get_collection_names(self) -> List[str]:
        return self.db_handle.list_collection_names()


    def find_document(self, collection_name: str, server_name: str) -> Tuple[dict, datetime.date]:
        collection = self.db_handle[collection_name]
        doc = collection.find_one({'system_info.hostname': server_name.lower()}, projection={'_id': False})
        self.__apply_projection(doc)
        return doc


    def insert_documents(self, collection_name: str, documents: List[dict]) -> None:
        self.db_handle[collection_name].insert_many(documents)


    def create_collection(self, collection_name: str) -> None:
        self.db_handle.create_collection(collection_name)
        return


    def drop_collection(self, collection_name: str) -> None:
        self.db_handle.drop_collection(collection_name)
        return


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

        system_info.pop("errors", None)
        wildfly_info.pop("errors", None)

        return

    
    def __get_dict(self, ddiff: DeepDiff, entry_key: str, value_src: dict):
        ret = {}

        if entry_key in ddiff:

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