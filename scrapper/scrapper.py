from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options

import pandas as pd
from time import sleep
import os
import zipfile
import datetime


FROM = "2023-09-01"
TO = "2023-11-05"


def initialize_selenium():
    options = Options()

    options.set_preference("browser.download.folderList", 2)
    if not os.path.exists(os.getcwd() + '/downloads'):
        os.mkdir(os.getcwd() + '/downloads')
    options.set_preference("browser.download.dir", os.getcwd() + '/downloads')
    options.add_argument("-headless") 
    browser = webdriver.Firefox(options=options)
    browser.get('https://www.binance.com/en/landing/data')
    sleep(3)
    browser.find_element(By.CSS_SELECTOR, '#onetrust-accept-btn-handler').click()
    sleep(.3)
    return browser


def date_range(first, last, step=1):
    date = first
    while date < last:
        yield date
        date += datetime.timedelta(step)


def download_dataset(dataset, symb, date):
    browser = initialize_selenium()

    browser.find_element(By.CSS_SELECTOR, ".css-1mizem0").send_keys(dataset)
    sleep(3)

    list_item = browser.find_element(By.XPATH, f"//*[text()='{dataset}']")
    ActionChains(browser).move_to_element(list_item).perform()
    sleep(.3)

    for coin_m in browser.find_elements(By.XPATH, "//*[text()='COIN-M']"):
        if coin_m.is_displayed():
            break
    
    coin_m.click()
    sleep(1.5)

    browser.find_element(By.CSS_SELECTOR, '.landing-ui-simple-dropdown[name="symbolList"]').click()
    sleep(.3)
    browser.find_element(By.CSS_SELECTOR, 'input[placeholder="Search for Symbol (Max: 5)"]').send_keys(symb)
    sleep(.3)
    browser.find_element(By.ID, symb).click()
    sleep(.3)
    browser.find_element(By.CSS_SELECTOR, '.landing-ui-simple-dropdown[name="symbolList"]').click()
    sleep(.3)

    gran_list = browser.find_elements(By.CSS_SELECTOR, '.landing-ui-simple-dropdown[name="granularityList"]')
    if len(gran_list) == 1:
        gran_list = gran_list[0]
        gran_list.click()
        sleep(.3)
        browser.find_element(By.CSS_SELECTOR, 'input[placeholder="Search for Granularity"]').send_keys('1d')
        sleep(.3)
        browser.find_element(By.ID, '1d').click()
        sleep(.3)

    for idx, date_inp in enumerate(browser.find_elements(By.CSS_SELECTOR, 'input[placeholder=YYYY-MM-DD]')):
        date_inp.send_keys(date.isoformat() if idx == 0 else (date + datetime.timedelta(6)).isoformat())
        date_inp.send_keys(Keys.ENTER)
        sleep(.3)
    
    browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
    sleep(2)
    browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()

    checks = 0
    while True:
        sleep(4)

        files = os.listdir(os.getcwd() + '/downloads')
        bads = 0
        for file in files:
            if not(file.endswith('.zip') or file.endswith('.csv')):
                bads += 1

        if bads == 0:
            checks += 1
            if checks == 3:
                break
        else:
            checks = 0

    result = []
    for filename in os.listdir(os.getcwd() + '/downloads'):
        if filename.endswith('.zip'):
            result.append(os.getcwd() + '/downloads/' +  filename.removesuffix('.zip') + '.csv')
            zipfile.ZipFile(os.getcwd() + '/downloads/' + filename).extractall(os.getcwd() + '/downloads')
            os.remove(os.getcwd() + '/downloads/' + filename)

    result.sort()

    pdates = set()
    for pdate in date_range(date, (date + datetime.timedelta(7))):
        for fname in result:
            if pdate.isoformat() in fname:
                pdates.add(pdate)
                break

    browser.quit()
    return result, pdates


if __name__ == '__main__':
    for begin_date in reversed(list(date_range(datetime.date.fromisoformat(FROM), datetime.date.fromisoformat(TO), 7))):
        ticks_files_raw, ticks_dates = download_dataset("Book Ticker", "BTCUSD_PERP", begin_date)
        candles_files_raw, candles_dates = download_dataset("K-Line", "BTCUSD_PERP", begin_date)

        drange = list(date_range(begin_date, begin_date + datetime.timedelta(7)))
        drange = [date for date in drange if (date in ticks_dates and date in candles_dates)]

        ticks_files = [ticks_files_raw[idx] for idx, date in enumerate(ticks_dates) if date in drange]
        candles_files = [candles_files_raw[idx] for idx, date in enumerate(candles_dates) if date in drange]

        for date, ticks_file, candles_file in zip(drange, ticks_files, candles_files):
            ticks = pd.read_csv(ticks_file)
            candles = pd.read_csv(candles_file)

            min_bid = ticks['best_bid_price'].min()
            max_ask = ticks['best_ask_price'].max()
            mid = ((ticks['best_bid_price'] + ticks['best_ask_price']) / 2).mean()
            volume = candles['volume'].iloc[0]
            df = pd.DataFrame({'min_bid': min_bid, 'max_ask': max_ask, 'mid': mid, 'volume': volume}, index=[date.isoformat()])

            if not os.path.exists(os.getcwd() + '/res'):
                os.mkdir(os.getcwd() + '/res')
            df.to_csv(os.getcwd() + '/res/' + date.isoformat() + '.csv', index_label='date')

        for f in ticks_files_raw:
            os.remove(f)
        for f in candles_files_raw:
            os.remove(f)
