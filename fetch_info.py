import re
import time
import shutil
import random
import logging
from datetime import date
from typing import Optional, Any

import typer
import joblib
import pandas as pd
from tqdm import tqdm
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    before_sleep_log,
    RetryError,
    retry_if_exception_type,
)

from utils.post_processing import adjust_price_, auto_marking_, parse_price
from collect_list import JS_PATCH

LOGGER = logging.getLogger(__name__)


def navigate_to_a_page(browser: webdriver.Chrome, url: str):
    try:
        browser.get(url)
        # Bypass disable-devtool
        browser.execute_script("window.__30f1fb31232ca3e80fba75ceb4253b35__ = true;")
    except Exception as e:
        print(f"Failed to navigate to the page: {e}")
        raise e

    # Second layer of defense
    browser.execute_script(JS_PATCH)
    # typer.echo("✅ Patch applied successfully!")

    # Wait for the "下一頁" (next page) link to be present
    # This helps ensure the page content is loaded before we start scraping
    WebDriverWait(browser, 10).until(ec.visibility_of_element_located((By.CSS_SELECTOR, "div.title")))
    # typer.echo("Title found, page content loaded.")

    time.sleep(random.random() * 5 + 1)

    # For debugging purposes
    with open("/tmp/ramdisk/tmp.html", "w") as fout:
        _ = fout.write(browser.page_source)


class NotExistException(Exception):
    pass


def get_attributes(soup):
    result = {}
    try:
        result["養寵物"] = "No" if "不可養寵物" in soup.select_one("section.service").text else "Yes"
    except AttributeError:
        result["養寵物"] = None
    contents = soup.select_one("div.house-detail-content-left div.content").children
    for item in contents:
        try:
            name = item.select_one("div span.label").text
            if name in ("租金含", "車位費", "管理費"):
                result[name] = name = item.select_one("div div.text").text.strip()
        except AttributeError as e:
            print(e)
            continue
    service_list = soup.select_one("div.service-facility").select("dl")
    services = []
    for item in service_list:
        if "del" in item["class"]:
            continue
        services.append(item.select_one("dd").text.strip())
    result["提供設備"] = ", ".join(services)
    # attributes = soup.select_one("div.pattern").find_all("span")
    # for i, key in enumerate(("格局", "坪數", "樓層", "型態")):
    #     result[key] = attributes[i * 2].text.strip()
    return result


@retry(
    reraise=False,
    retry=retry_if_exception_type(TimeoutException),
    stop=stop_after_attempt(2),
    wait=wait_fixed(1),
    before_sleep=before_sleep_log(LOGGER, logging.INFO),
)
def get_page(browser: webdriver.Chrome, listing_id):
    navigate_to_a_page(browser, f"https://rent.591.com.tw/home/{listing_id}".strip())
    soup = BeautifulSoup(browser.page_source, "lxml")
    title = soup.select_one("div.title")
    if title and "不存在" in str(title.text):
        raise NotExistException()
    return soup


def get_listing_info(browser: webdriver.Chrome, listing_id: str):
    try:
        soup = get_page(browser, listing_id)
    except RetryError:
        # Still attempt to fetch the page content
        typer.echo("RetryError encountered... Trying to parse whatever is on the page.")
        soup = BeautifulSoup(browser.page_source, "lxml")
    result: dict[str, Any] = {"id": listing_id}
    result["title"] = soup.select_one(".title h1").text
    result["addr"] = soup.select_one("div.address div").text.strip() if soup.select_one("div.address div") else ""
    complex = soup.select_one("div.address p a")
    if complex:
        result["社區"] = complex.text.strip()
    result["price"] = parse_price(soup.select_one("div.house-price").text)
    result["desc"] = soup.select_one("div.house-condition-content").text.strip()
    result["poster"] = re.sub(r"\s+", " ", soup.select_one("p.base-info-pc").text.strip())
    result.update(get_attributes(soup))
    return result


def main(
    source_path: str = "cache/listings.jbl",
    data_path: Optional[str] = None,
    output_path: Optional[str] = None,
    limit: int = -1,
    headless: bool = False,
):
    listing_ids = joblib.load(source_path)
    df_original: Optional[pd.DataFrame] = None
    if data_path:
        if data_path.endswith(".pd"):
            df_original = pd.read_pickle(data_path)
        else:
            df_original = pd.read_csv(data_path)
        listing_ids = list(set(listing_ids) - set(df_original.id.values.astype("str")))
        print(len(listing_ids))

    if limit > 0:
        listing_ids = listing_ids[:limit]

    print(f"Collecting {len(listing_ids)} entries...")

    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    # Block loading of all images on the web page
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)

    browser = webdriver.Chrome(options=options)

    data = []
    for id_ in tqdm(listing_ids, ncols=100):
        try:
            data.append(get_listing_info(browser, id_))
        except NotExistException:
            LOGGER.warning(f"Does not exist: {id_}")
            pass
        time.sleep(random.random() * 5)

    df_new = pd.DataFrame(data)
    optional_fields = ("租金含", "車位費", "管理費")
    for field in optional_fields:
        if field not in df_new:
            df_new[field] = None
    df_new = auto_marking_(df_new)
    df_new = adjust_price_(df_new)
    df_new["fetched"] = date.today().isoformat()
    if df_original is not None:
        df_new = pd.concat([df_new, df_original], axis=0).reset_index(drop=True)

    if output_path is None and data_path is None:
        # default output path
        output_path = "cache/df_listings.csv"
    elif output_path is None and data_path:
        output_path = data_path
        shutil.copy(data_path, data_path + ".bak")

    df_new["link"] = "https://rent.591.com.tw/rent-detail-" + df_new["id"].astype("str") + ".html"
    column_ordering = [
        "mark",
        "title",
        "price",
        "price_adjusted",
        "link",
        "addr",
        "社區",
        "車位費",
        "管理費",
        "poster",
        "養寵物",
        "提供設備",
        # "格局",
        # "坪數",
        # "樓層",
        # "型態",
        "id",
        "fetched",
        "desc",
    ]
    print(df_new.drop("desc", axis=1).sample(min(df_new.shape[0], 10)))
    df_new[column_ordering].to_csv(output_path, index=False)
    print("Finished!")


if __name__ == "__main__":
    typer.run(main)
