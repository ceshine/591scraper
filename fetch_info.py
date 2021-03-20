import time
import shutil
import random
import logging
from datetime import date
from typing import Optional

import typer
import joblib
import requests
import pandas as pd
from tqdm import tqdm
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_fixed, before_sleep_log
from requests.exceptions import HTTPError

from utils.post_processing import adjust_price_, auto_marking_

LOGGER = logging.getLogger(__name__)


def get_attributes(soup):
    result = {}
    attributes = soup.select_one("ul.labelList").find_all("li")
    for attr in attributes:
        key = attr.find("div", attrs={"class": "one"}).text
        if key in ['養寵物', '管理費', '車 位']:
            result[key] = attr.find(
                "div", attrs={"class": "two"}).text.replace("：", "")
    attributes = soup.select_one("div.detailInfo").find_all("li")
    for attr in attributes:
        key, value = (x.strip() for x in attr.text.split(":"))
        if key in ['格局', '樓層', '坪數', '型態', '社區']:
            result[key] = value
    return result


def retry_condition(exception):
    """Return True if we should retry (in this case when it's an IOError), False otherwise"""
    if isinstance(exception, (HTTPError, AttributeError)):
        print(f'HTTP error occurred: {exception}')  # Python 3.6
        return True
    return False


@retry(
    reraise=True, retry=retry_condition,
    stop=stop_after_attempt(5), wait=wait_fixed(10),
    before_sleep=before_sleep_log(LOGGER, logging.INFO))
def get_page(listing_id):
    res = requests.get(
        f"https://rent.591.com.tw/rent-detail-{listing_id}.html")
    assert res.status_code == 200
    return res.text


def get_listing_info(listing_id):
    soup = BeautifulSoup(get_page(listing_id), "lxml")
    result = {"id": listing_id}
    result['title'] = soup.select_one("span.houseInfoTitle").text
    result['addr'] = soup.select_one("span.addr").text
    tmp = soup.select_one("div.detailInfo")
    result['price'] = int(tmp.select_one("div.price").text.split(" ")[
                          0].strip().replace(",", ""))
    result['expired_at'] = tmp.find_all("span")[-1].text.split("：")[-1]
    result['desc'] = soup.select_one("div.houseIntro").text.strip()
    result['explain'] = soup.select_one("div.explain").text.strip()
    result['poster'] = soup.select_one(
        "div.avatarRight").find_all("div")[0].text.strip()
    result.update(get_attributes(soup))
    return result


def main(
    source_path: str = "cache/listings.jbl", data_path: Optional[str] = None,
    output_path: Optional[str] = None, limit: int = -1
):
    listing_ids = joblib.load(source_path)
    df_original: Optional[pd.DataFrame] = None
    if data_path:
        if data_path.endswith(".pd"):
            df_original = pd.read_pickle(data_path)
        else:
            df_original = pd.read_csv(data_path)
        listing_ids = list(
            set(listing_ids) - set(df_original.id.values.astype("str"))
        )
        print(len(listing_ids))

    if limit > 0:
        listing_ids = listing_ids[:limit]

    print(f"Collecting {len(listing_ids)} entries...")

    data = []
    for id_ in tqdm(listing_ids, ncols=100):
        try:
            data.append(get_listing_info(id_))
        except AttributeError:
            print(f"Skipped {id_}")
            pass
        time.sleep(random.random() * 5)

    df_new = pd.DataFrame(data)
    df_new = auto_marking_(df_new)
    df_new = adjust_price_(df_new)
    df_new["fetched"] = date.today().isoformat()
    if df_original is not None:
        df_new = pd.concat([df_new, df_original],
                           axis=0).reset_index(drop=True)

    if output_path is None and data_path is None:
        # default output path
        output_path = "cache/df_listings.csv"
    elif output_path is None and data_path:
        output_path = data_path
        shutil.copy(data_path, data_path + ".bak")

    df_new["link"] = "https://rent.591.com.tw/rent-detail-" + \
        df_new["id"].astype("str") + ".html"
    if "mark" not in df_new:
        df_new["mark"] = ""
    column_ordering = [
        "mark", "title", "price", "price_adjusted", "link", "addr",
        "explain", "社區", "車 位", "管理費",
        "poster", "養寵物", "格局", "坪數", "樓層", "型態",
        "expired_at", "id", "desc", "fetched"
    ]
    df_new[column_ordering].to_csv(output_path, index=False)
    print("Finished!")


if __name__ == "__main__":
    typer.run(main)
