import os
import time
import random
from typing import List
from urllib.parse import urlparse, parse_qs

import typer
import joblib
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup

URL = os.environ["X591URL"]


def main(output_path: str = "cache/listings.jbl", max_pages: int = 10, quiet: bool = False):
    try:
        region = parse_qs(urlparse(URL).query)['region'][0]
    except AttributeError as e:
        print("The URL must have a 'region' query argument!")
        raise e
    options = webdriver.ChromeOptions()
    if quiet:
        options.add_argument('headless')
    browser = webdriver.Chrome(options=options)
    browser.get(URL)
    try:
        browser.find_element_by_css_selector(
            f"dd[data-id=\"{region}\"]").click()
    except NoSuchElementException:
        pass
    time.sleep(2)
    listings: List[str] = []
    for i in range(max_pages):
        print(f"Page {i+1}")
        soup = BeautifulSoup(browser.page_source, "lxml")
        for item in soup.find_all("section", attrs={"class": "vue-list-rent-item"})
            link = item.find("a")
            listings.append(link.attrs["href"].split("-")[-1].split(".")[0])
        browser.find_element_by_class_name('pageNext').click()
        time.sleep(random.random() * 5)
        try:
            browser.find_element_by_css_selector('a.last')
            break
        except NoSuchElementException:
            pass
    print(len(set(listings)))
    joblib.dump(listings, output_path)
    print(f"Done! Collected {len(listings)} entries.")


if __name__ == "__main__":
    typer.run(main)
