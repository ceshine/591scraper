"""Collects rental listing IDs from 591.com.tw based on a provided URL.

This script navigates to a specified 591.com.tw rental listing page,
extracts listing IDs, and saves them to a joblib file.

It supports pagination to collect IDs from multiple pages.

Environment Variables:
    X591URL: The base URL for the 591.com.tw rental listings. This URL
             must contain a 'region' query parameter.

Functions:
    main: The main function to execute the listing collection process.
"""

import os
from urllib.parse import urlparse, parse_qs, urljoin

import typer
import joblib
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

URL = os.environ["X591URL"]

JS_PATCH = """
window.addEventListener('beforeunload', function (e) {
    // Cancel the event
    e.preventDefault();
    // Chrome requires returnValue to be set to an empty string
    e.returnValue = '';
});

// Override the history object's methods
window.history.back = function() { console.log('history.back() blocked.'); };
window.history.forward = function() { console.log('history.forward() blocked.'); };
window.history.go = function() { console.log('history.go() blocked.'); };

// You can also try to lock down the location object.
// Note: Overriding `window.location.href` directly is difficult and not recommended.
// It's better to override the methods that change it.
window.location.assign = function() { console.log('location.assign() blocked.'); };
window.location.replace = function() { console.log('location.replace() blocked.'); };

// Disable the timer that the disable-devtools library uses for its checks.
// This might break other site functionality, but is very effective.
window.setInterval = function() { console.log('setInterval() blocked by Selenium patch.'); };
"""


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
    typer.echo("✅ Patch applied successfully!")

    # Wait for the "下一頁" (next page) link to be present
    # This helps ensure the page content is loaded before we start scraping
    try:
        WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.LINK_TEXT, "下一頁")))
        typer.echo("Next page link found, page content loaded.")
    except Exception:
        typer.echo("Next page link not found, proceeding anyway (might be a single page result).")

    # For debugging purposes
    # with open("/tmp/ramdisk/tmp.html", "w") as fout:
    #     _ = fout.write(browser.page_source)


def main(output_path: str = "cache/listings.jbl", max_pages: int = 10, quiet: bool = False):
    try:
        region = parse_qs(urlparse(URL).query)["region"][0]
    except (AttributeError, KeyError) as e:
        print("The URL must have a 'region' query argument!")
        raise e
    options = webdriver.ChromeOptions()
    if quiet:
        options.add_argument("--headless")

    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    browser = webdriver.Chrome(options=options)
    typer.echo("Browser initialized.")

    # Navigate to the specified URL
    navigate_to_a_page(browser, URL)

    listings: set[str] = set()
    for i in range(max_pages):
        print(f"Page {i + 1}")
        soup = BeautifulSoup(browser.page_source, "lxml")

        for item in soup.find_all("div", attrs={"class": "item-info-title"}):
            link = item.find("a")
            if link is not None and getattr(link, "attrs", None) is not None:
                listings.add(link.attrs["href"].split("/")[-1])

        next_page_link = soup.find("a", string="下一頁")

        if i == max_pages - 1:
            typer.echo("Reached maximum pages. Exiting...")
            break

        new_link = str(next_page_link.attrs["href"]).strip()

        if not next_page_link or new_link in ("", "#"):
            typer.echo("No more pages to scrape. Exiting...")
            break

        new_url = urljoin(browser.current_url, new_link)
        navigate_to_a_page(browser, new_url)

        # An alternative approach: Click the next page link using Selenium
        # browser.find_element(By.LINK_TEXT, "下一頁").click()

    joblib.dump(list(listings), output_path)
    print(f"Done! Collected {len(listings)} entries.")

    # Uncomment to pause before closing the browser
    # import time
    # time.sleep(10)

    browser.quit()


if __name__ == "__main__":
    typer.run(main)
