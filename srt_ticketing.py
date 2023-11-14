import yaml
import traceback
from prettytable import PrettyTable
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.common.alert import Alert
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from bs4 import Tag
import requests

import threading

event = threading.Event()

SRT_PHONE_NUM = ""
SRT_PASSWORD = ""
TELEGRAM_TOKEN = ""
TELEGRAM_CHAT_ID = ""


CONFIRM = '//*[@id="wrap"]/div[4]/div/div[2]/div[7]/a'

purchase_btn = "//*[@id='list-form']/fieldset/div[11]/a[1]"


def load_config():
    global SRT_PHONE_NUM
    global SRT_PASSWORD
    global TELEGRAM_TOKEN
    global TELEGRAM_CHAT_ID
    try:
        with open("./config.yaml", "r") as f:
            config = yaml.full_load(f)
            SRT_PHONE_NUM = config["SRT_PHONE_NUM"]
            SRT_PASSWORD = config["SRT_PASSWORD"]
            TELEGRAM_TOKEN = config["TELEGRAM_TOKEN"]
            TELEGRAM_CHAT_ID = config["TELEGRAM_CHAT_ID"]
    except Exception:
        print("Does not exist config.yaml")


def remove_blank(text):
    return " ".join(text.strip().split())


def find_element(driver, xpath):
    try:
        return driver.find_element(by=By.XPATH, value=xpath)
    except NoSuchElementException:
        return None


def get_seat(driver: webdriver.Chrome, select):
    row = int(select / 2) + 1
    seat = 6 + (select % 2)
    txt = driver.find_element(
        by=By.XPATH,
        value=f"//*[@id='result-form']/fieldset/div[6]/table/tbody/tr[{row}]/td[{seat}]/a/span",
    ).text
    btn = driver.find_element(
        by=By.XPATH,
        value=f"//*[@id='result-form']/fieldset/div[6]/table/tbody/tr[{row}]/td[{seat}]/a",
    )
    return remove_blank(txt), btn


def send_telegram_message(message):
    if TELEGRAM_TOKEN == "" or TELEGRAM_CHAT_ID == "":
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={message}"
        requests.post(url)
    except Exception as e:
        print(e)


def login(driver):
    if SRT_PHONE_NUM == "" or SRT_PASSWORD == "":
        return
    try:
        driver.find_element(by=By.ID, value="srchDvNm01").send_keys(
            SRT_PHONE_NUM
        )  # 휴대폰 번호 입력
        driver.find_element(by=By.ID, value="hmpgPwdCphd01").send_keys(
            SRT_PASSWORD
        )  # 비밀번호 입력
        driver.find_element(
            by=By.XPATH,
            value='//*[@id="login-form"]/fieldset/div[1]/div[1]/div[2]/div/div[2]/input',
        ).click()  # 로그인 클릭

        ######################## 휴대전화번호 로그인
        # driver.find_element(by=By.ID, value="srchDvCd3").click()  # 휴대폰 로그인 Check
        # driver.find_element(by=By.ID, value="srchDvNm03").send_keys(
        #     SRT_PHONE_NUM
        # )  # 휴대폰 번호 입력
        # driver.find_element(by=By.ID, value="hmpgPwdCphd03").send_keys(
        #     SRT_PASSWORD
        # )  # 비밀번호 입력
        # driver.find_element(
        #     by=By.XPATH,
        #     value='//*[@id="login-form"]/fieldset/div[1]/div[1]/div[4]/div/div[2]/input',
        # ).click()  # 로그인 클릭
    except Exception as e:
        print(e)


def main():
    load_config()

    options = Options()
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    driver = webdriver.Chrome(service=Service(), options=options)
    driver.implicitly_wait(10)
    wait = WebDriverWait(driver, 10)

    driver.get("https://etk.srail.kr/cmc/01/selectLoginForm.do?pageId=TK0701000000")
    login(driver)

    while True:
        print("After Login, Do you go to the page with the seat you want? (y/n)")
        a = input()
        if a == "y" or a == "Y":
            break

    doc = driver.page_source
    soup = BeautifulSoup(doc, "html.parser")

    #
    table: Tag = soup.find_all("table")[0]
    rows = table.find("tbody").find_all("tr")

    # Print Table
    print("\n" + table.find("thead").find("th").text, sep="")
    t = PrettyTable(
        ["No.", "열차번호", "출발역", "도착역", "호실"],
    )
    for field in t.field_names:
        t.align[field] = "c"
    no = 1
    for row in rows:
        cols = row.find_all("td")[2:5]
        txt_cols = [remove_blank(col.text) for col in cols]
        t.add_row([no] + txt_cols + ["특실"])
        t.add_row([no + 1] + txt_cols + ["일반실"])
        no += 2
    print(t)

    # Get num wanted
    print("\nInput Num you want.(ex: 1,4)")
    selects = input()
    selects = [int(select.strip()) - 1 for select in selects.split(",")]

    print("run")
    send_telegram_message("매크로 시작")
    macro_url = driver.current_url
    while True:
        try:
            driver.refresh()
            driver.implicitly_wait(10)
            for select in selects[:]:
                txt, btn = get_seat(driver, select)
                if "예약하기" in txt:
                    # wait.until(lambda driver: btn.is_enabled() and btn.is_displayed())
                    driver.implicitly_wait(10)
                    btn.click()
                    print("click reservation")
                    try:
                        while True:
                            alert = Alert(driver)
                            alert.accept()
                            print(f"click alert({alert.text})")
                            driver.implicitly_wait(10)
                    except NoAlertPresentException:
                        pass
                    driver.implicitly_wait(10)

                    page_source = driver.page_source
                    if "20분 이내 열차는 예약하실 수 없습니다" in page_source:
                        selects.remove(select)
                    elif "결제하기" in page_source:
                        print("reservation successful")
                        send_telegram_message("예매 성공")
                    elif "잔여석 없음" in page_source:
                        print("no seat")
                    else:
                        print("reservation fail")

                    if driver.current_url != macro_url:
                        driver.back()
                        print("back driver")
                        driver.implicitly_wait(10)
                    break
                    # page_source = driver.page_source
                    # if "선택좌석 예약하기" in page_source:
                    #     print("선택좌석 예약하기")
                    # elif "20분 이내 열차는 예약하실 수 없습니다" in page_source:
                    #     selects.remove(select)
                    #     driver.back()
                    #     driver.implicitly_wait(10)
                    # elif "잔여석" in page_source:
                    #     print("No seat")
                    #     driver.back()
                    #     driver.implicitly_wait(10)
                    # elif "결제하기" in page_source:
                    #     print("reservation successful")
                    #     send_telegram_message("예매 성공")
                    #     driver.back()
                    #     driver.implicitly_wait(10)
                    # else:
                    #     time.sleep(999999)
                    # print("end")
        except KeyboardInterrupt:
            print("exit")
            send_telegram_message("매크로 종료")
            driver.quit()
        except Exception as e:
            tb_str = traceback.format_exception(
                etype=type(e), value=e, tb=e.__traceback__
            )
            print("".join(tb_str))
            # print(e)
            driver.refresh()
            driver.implicitly_wait(10)
            continue


if __name__ == "__main__":
    main()
