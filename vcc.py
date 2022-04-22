import requests
from dotenv import load_dotenv
import os
import pandas as pd
import time

load_dotenv("_env/.env")
customer = os.getenv("VCC_CUSTOMER")
api_key = os.getenv("VCC_API_KEY")


class VccApi:

    def __init__(self, url: str):
        self.url = f"https://{customer}:{api_key}@{customer}.asp.virtual-call-center.eu/v2{url}"
        self.data = self.get_data()

    def get_data(self):
        with requests.get(url=self.url) as response:
            response.raise_for_status()
            json_data = response.json()
            list_data = json_data["response"]
            # pprint(list_data)
            df = pd.DataFrame(list_data)
            return df


class VccUsers(VccApi):

    def __init__(self, url):
        super().__init__(url)
        # self.export_data = pd.DataFrame
        self.export_data = self.process_data()

    def process_data(self):
        df_users = self.data.loc[
            (self.data["group_name"] == "operator") &
            (self.data["status"] == "active") &
            (
                    (self.data["teams_name"].str.contains("Sales")) |
                    (self.data["teams_name"].str.contains("Customer Service"))
            )
        ]
        # print(df_users)
        return df_users


class VccRealTime(VccApi):

    def __init__(self, url):
        super(VccRealTime, self).__init__(url)
        self.statuses = {"AFTERWORK": "Afterwork", "AVAILABLE4CALL": "Available", "CALL": "Call", "EMAIL": "Email",
                         "HOLD": "Hold", "PREWORK": "Prework", "RINGING": "Ringing", "TICKET_BROWSING": "Ticket",
                         "UNAVAILABLE": "Unavailable", "WAITING4CALL": "Waiting for call",
                         "WAITING4RECALL": "Waiting for call back", "ORIGINATOR_RINGING": "Ringing", "AUX": "Break"}
        self.export_data = []

    def process_data(self, user_data: pd.DataFrame):
        merge_data = pd.merge(left=self.data, left_on="userId", right=user_data, right_on="userid")
        merge_data["state"].replace(self.statuses, inplace=True)
        merge_data["surname"] = merge_data["name"].str.split().str[-1]

        sales_data = merge_data.loc[merge_data["teams_name"].str.contains("Sales")]
        sales_data = sales_data.sort_values("surname")
        cs_data = merge_data.loc[merge_data["teams_name"].str.contains("Customer Service")]
        cs_data = cs_data.sort_values("surname")
        self.export_data = [sales_data[["name", "state"]], cs_data[["name", "state"]]]
        return [sales_data[["name", "state"]], cs_data[["name", "state"]]]

#
# users = VccUsers(url="/users")
#
#
# for i in range(5):
#     realtime = VccRealTime(url="/onlineusers")
#     # print(realtime.data)
#     realtime.process_data(user_data=users.export_data)
#     # print(realtime.export_data.groupby("state").count())
#     print("Sales: \n", realtime.export_data[0])
#     print("CS: \n", realtime.export_data[1])
#
#     # print(realtime.export_data[["name", "state", "teams_name"]])
#     time.sleep(30)
