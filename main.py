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


def start_source_browser():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    service = Service(executable_path=driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(url=url)
    username_field = driver.find_element(by=By.ID, value="Username")
    password_field = driver.find_element(by=By.ID, value="Password")
    submit_button = driver.find_element(by=By.XPATH, value="/html/body/div[2]/div/div/div/div/div[2]/form/div["
                                                           "5]/div/button")
    username_field.send_keys(username)
    password_field.send_keys(password)
    submit_button.click()
    return driver


def get_source_data(driver: webdriver.Chrome):
    driver.refresh()
    data = driver.page_source
    soup = BeautifulSoup(markup=data, features="html.parser")
    tables = [
        soup.select_one(selector="#WallboardCZ #Daily"),
        soup.select_one(selector="#WallboardCZ #LeadAvgTime"),
        soup.select_one(selector="#WallboardSK #Daily"),
        soup.select_one(selector="#WallboardSK #LeadAvgTime")
    ]
    dataframes = [pd.read_html(f"<html>{table}</html>") for table in tables]
    driver.close()
    dataframes = [dataframe[0]for dataframe in dataframes]

    for df in dataframes:
        if df.isna().values.any():
            df.fillna(value="", inplace=True)

    return dataframes


@app.context_processor
def inject_load():
    rs_driver = start_source_browser()
    src_data = get_source_data(driver=rs_driver)
    now = datetime.datetime.now().strftime("%H:%M:%S")
    data = {f"tab_{i+1}": src_data[i] for i in range(len(src_data))}
    data["time"] = now
    return data


@app.before_first_request
def before_first_request():
    threading.Thread(target=update_data).start()


def update_data():
    with app.app_context():
        while True:
            turbo.push([turbo.replace(render_template("table_sales_cz.html"), "tab_1_div"),
                        turbo.replace(render_template("table_lead_cz.html"), "tab_2_div"),
                        turbo.replace(render_template("table_sales_sk.html"), "tab_3_div"),
                        turbo.replace(render_template("table_lead_sk.html"), "tab_4_div"),
                        turbo.replace(render_template("time.html"), "time_div"),
                        ])
            time.sleep(10)


@app.route("/")
def main_page():

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True, host="localhost")
