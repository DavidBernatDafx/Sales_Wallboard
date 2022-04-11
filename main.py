from flask import Flask, render_template
from turbo_flask import Turbo
from flask_bootstrap import Bootstrap
import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import datetime
from bs4 import BeautifulSoup
import pandas as pd
import threading

app = Flask(__name__)
# Bootstrap(app)
turbo = Turbo(app)
Bootstrap(app)

load_dotenv("_env/.env")
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
url = os.getenv("URL")
driver_path = os.path.join(os.getcwd(), "Chromedriver", "chromedriver.exe")
webapp_ip = os.getenv("WEB_APP_IP")

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
            soup.select_one(selector="#WallboardSK #LeadAvgAge")
        ]
        dataframes = []
        try:
            dataframes = [pd.read_html(f"<html>{table}</html>") for table in tables]
            # self.driver.close()
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


rs_web = Browser()
rs_web.do_login()


@app.context_processor
def inject_load():
    src_data = rs_web.get_source_data()
    print(src_data[0])
    now = datetime.datetime.now().strftime("%H:%M:%S")
    data = {f"tab_{i+1}": src_data[i] for i in range(len(src_data))}
    data["time"] = now
    return data


@app.before_first_request
def before_first_request():
    # threading.Thread(target=Browser.get_source_data).start()
    threading.Thread(target=update_data).start()


def update_data():
    with app.app_context():
        while True:
            turbo.push([turbo.replace(render_template("wallboard.html"), "tables"),
                        turbo.replace(render_template("time.html"), "time_div"),
                        ])
            time.sleep(30)


@app.route("/")
def main_page():

    return render_template("index.html")


if __name__ == "__main__":
    app.run(host=webapp_ip)
