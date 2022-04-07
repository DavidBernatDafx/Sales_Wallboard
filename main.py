from flask import Flask, render_template
from turbo_flask import Turbo
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
turbo = Turbo(app)



load_dotenv("_env/.env")
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
url = os.getenv("URL")
driver_path = os.path.join(os.getcwd(), "Chromedriver", "chromedriver.exe")


class Browser:
    """Class that represents Chrome driver operations with data source webpage"""

    def __init__(self):
        self.options = Options()
        # self.options.add_argument("--headless")
        # self.options.add_argument("--disable-gpu")
        self.service = Service(executable_path=driver_path)
        self.driver = webdriver.Chrome(service=self.service, options=self.options)
        # self.driver.minimize_window()
        self.load_rslife()
        self.login_rslife(user=username, pswd=password)
        self.dataframes = self.get_data()
        self.data_changed = False

    def load_rslife(self):
        self.driver.get(url=url)

    def login_rslife(self, user: str, pswd: str):
        username_field = self.driver.find_element(by=By.ID, value="Username")
        password_field = self.driver.find_element(by=By.ID, value="Password")
        submit_button = self.driver.find_element(by=By.XPATH, value="/html/body/div[2]/div/div/div/div/div["
                                                                    "2]/form/div[5]/div/button")
        username_field.send_keys(user)
        password_field.send_keys(pswd)
        submit_button.click()

    def get_data(self):
        data = self.driver.page_source
        soup = BeautifulSoup(markup=data, features="html.parser")
        tables = [
            soup.select_one(selector="#WallboardCZ #Daily"),
            soup.select_one(selector="#WallboardCZ #LeadAvgTime"),
            soup.select_one(selector="#WallboardSK #Daily"),
            soup.select_one(selector="#WallboardSK #LeadAvgTime")
        ]
        dataframes = [pd.read_html(f"<html>{table}</html>") for table in tables]
        self.driver.close()
        return [dataframe[0] for dataframe in dataframes]


def update_data():
    with app.app_context():
        while True:
            turbo.push([turbo.replace(render_template("table_1.html"), "tab_1"),
                        turbo.replace(render_template("time.html"), "time_div"),
                        ])
            time.sleep(10)


@app.before_first_request
def before_first_request():
    threading.Thread(target=update_data).start()


@app.context_processor
def inject_load():
    browser = Browser()
    now = datetime.datetime.now().strftime("%H:%M")

    data = {"tab_1": browser.dataframes[0],
            "time": now
            }
    # print(data)
    return data








@app.route("/")
def main_page():

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True, host="localhost")
