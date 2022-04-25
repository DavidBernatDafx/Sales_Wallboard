import requests.exceptions
from flask import Flask, render_template
from turbo_flask import Turbo
from flask_bootstrap import Bootstrap
import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
import datetime
from bs4 import BeautifulSoup
import pandas as pd
import threading
from vcc import VccUsers, VccRealTime

app = Flask(__name__)
# Bootstrap(app)
turbo = Turbo(app)
Bootstrap(app)


load_dotenv(os.path.join(os.getcwd(), "_env/.env"))
username = "david.bernat"
password = os.getenv("PASSWORD")
url = os.getenv("URL")
driver_path = os.path.join(os.getcwd(), "Chromedriver", "chromedriver.exe")
webapp_ip = os.getenv("WEB_APP_IP")

today = datetime.datetime.now()
start = today.replace(hour=9, minute=0, second=0)
end = today.replace(hour=17, minute=30, second=0)
shift_duration = end - start


class Browser:

    def __init__(self):
        self.options = Options()
        self.options.add_argument("--headless")
        self.options.add_argument("--disable-gpu")
        self.service = Service(executable_path=driver_path)
        self.driver = webdriver.Chrome(service=self.service, options=self.options)
        self.driver.minimize_window()
        self.driver.get(url=url)
        self.dataframes = []

    def do_login(self):
        username_field = self.driver.find_element(by=By.ID, value="Username")
        password_field = self.driver.find_element(by=By.ID, value="Password")
        submit_button = self.driver.find_element(by=By.XPATH, value="/html/body/div[2]/div/div/div/div/div["
                                                                    "2]/form/div[5]/div/button")
        for i in range(9):
            username_field.send_keys(Keys.BACKSPACE)
            time.sleep(1)
        username_field.send_keys(username)
        password_field.send_keys(password)
        submit_button.click()

    def get_source_data(self):
        self.driver.refresh()
        time.sleep(1)
        data = self.driver.page_source
        soup = BeautifulSoup(markup=data, features="html.parser")
        tables = [
            soup.select_one(selector="#WallboardCZ #Daily"),
            soup.select_one(selector="#WallboardCZ #LeadAvgAge"),
            soup.select_one(selector="#WallboardSK #Daily"),
            soup.select_one(selector="#WallboardSK #LeadAvgAge"),
            soup.select_one(selector="#WallboardPL #Daily"),
            soup.select_one(selector="#WallboardPL #LeadAvgAge")
        ]
        dataframes = []
        try:
            dataframes = [pd.read_html(f"<html>{table}</html>") for table in tables]
        except ValueError:
            dataframes = self.dataframes
        else:
            dataframes = [dataframe[0] for dataframe in dataframes]

            for df in dataframes:
                if df.isna().values.any():
                    df.fillna(value="", inplace=True)
            self.dataframes = dataframes
        finally:
            return dataframes


def evaluate_data(col_plan: int, col_current: int):
    global shift_duration
    global start
    now = datetime.datetime.now()
    duration_progress = now - start
    duration_percentage = duration_progress / shift_duration * 100

    if col_plan != 0:
        plan_percentage = col_current / col_plan * 100
        if col_current >= col_plan:
            return "green"
        elif plan_percentage * 0.9 < duration_percentage:
            return "red"
        else:
            return "white"
    else:
        return "white"


rs_web = Browser()
rs_web.do_login()
vcc_users = VccUsers(url="/users")
old_vcc_data = []
old_compass_data = []


@app.context_processor
def inject_load():

    global old_compass_data
    global old_vcc_data
    try:
        vcc = VccRealTime(url="/onlineusers")
    except requests.exceptions.HTTPError:
        vcc_data = old_vcc_data
    else:
        vcc_data = vcc.process_data(user_data=vcc_users.export_data)
        old_vcc_data = vcc_data

    try:
        src_data = rs_web.get_source_data()
    except ValueError:
        src_data = old_compass_data
    else:
        old_compass_data = src_data

    # print(vcc_data[0])
    for i in range(0, len(src_data), 2):
        src_data[i]["res_sales"] = src_data[i].apply(
            lambda row: evaluate_data(row["Daily Target"], row["Actual"]), axis=1)
        src_data[i]["res_wol"] = src_data[i].apply(
            lambda row: evaluate_data(row["Daily Target WoL"], row["Actual WoL"]), axis=1)

    df_czsk = src_data[0][["Daily Target",
                           "Actual",
                           "Daily Target WoL",
                           "Actual WoL",
                           ]].add(src_data[2][["Daily Target",
                                               "Actual",
                                               "Daily Target WoL",
                                               "Actual WoL"]],
                                  fill_value=0)

    df_czsk.insert(0, "Sale Source", src_data[0]["Sale Source"])

    to_go = [
        df_czsk["Daily Target"] - df_czsk["Actual"],
        df_czsk["Daily Target WoL"] - df_czsk["Actual WoL"]
    ]

    df_czsk.insert(3, "To Go", to_go[0])
    df_czsk.insert(6, "To Go WoL", to_go[1])

    for i in range(df_czsk.shape[0]):
        if df_czsk.iloc[i, 3] < 0:
            df_czsk.iloc[i, 3] = 0
        if df_czsk.iloc[i, 6] < 0:
            df_czsk.iloc[i, 6] = 0

    df_czsk["res_sales"] = df_czsk.apply(
        lambda row: evaluate_data(row["Daily Target"], row["Actual"]), axis=1)
    df_czsk["res_wol"] = df_czsk.apply(
        lambda row: evaluate_data(row["Daily Target WoL"], row["Actual WoL"]), axis=1)

    now = datetime.datetime.now().strftime("%H:%M")
    data = {f"tab_{i+1}": src_data[i] for i in range(len(src_data))}
    data["tab_sum"] = df_czsk
    data["time"] = now
    data["vcc_sales"] = vcc_data[0]
    data["vcc_cs"] = vcc_data[1]
    # print(data["vcc"][0])

    return data


@app.before_first_request
def before_first_request():
    threading.Thread(target=update_data).start()


def update_data():
    with app.app_context():
        while True:
            turbo.push([turbo.replace(render_template("wallboard.html"), "tables"),
                        turbo.replace(render_template("time.html"), "time_div"),
                        turbo.replace(render_template("wallboard_vcc.html"), "vcc_tables"),
                        turbo.replace(render_template("wallboard_pl.html"), "pl_tables")
                        ])
            time.sleep(15)


@app.route("/sales")
def main_page():
    flags = ["https://upload.wikimedia.org/wikipedia/commons/a/a5/Flag-map_of_the_Czech_Republic.svg",
             "https://upload.wikimedia.org/wikipedia/commons/c/cb/Flag-map_of_Slovakia.svg"]
    year = today.year
    return render_template("index.html", flags=flags, year=year)


@app.route("/vcc")
def vcc_page():
    flag = "https://upload.wikimedia.org/wikipedia/commons/thumb/2/24/" \
           "Flag-map_of_Poland.svg/1024px-Flag-map_of_Poland.svg.png"
    year = today.year
    return render_template("vcc.html", flag=flag, year=year)


@app.route("/pl/sales")
def pl_sales():
    year = today.year
    return render_template("pl_sales.html", year=year)


if __name__ == "__main__":
    app.run(debug=True, host=webapp_ip)
