# 591 租房網自動抓取腳本

MIT LICENSE 開源，希望能幫助到有需要的人

## 使用說明

### Prerequisites

安裝所需套件 (Python 3.7+)：

```bash
pip install -r requirements.txt
```

本腳本使用 [Selenium + Chrome](https://chromedriver.chromium.org/getting-started) 抓取網頁，請按照網頁說明安裝 WebDriver for Chrome。

### Step 1: 抓取符合條件物件列表

首先將 591 搜尋頁面的網址存到 `X591URL` 環境變數，範例 (Bash):

````bash
export X591URL="https://rent.591.com.tw/?kind=1&order=money&orderType=asc&region=17&rentprice=10000,18000&other=lift"
```

以下範例會抓取最多 12 頁搜尋結果：

```bash
python collect_list.py --max-pages 12
````

預設結果存放位置是 `cache/listings.jbl`。

### Step 2: 抓取物件詳細資訊

直接執行 `fetch_info.py` 以獲取上一步抓取到的物件的詳細資訊，結果預設會存到 `cache/df_listings.csv`。

```bash
python fetch_info.py
```

如果你最近已經有抓過同一個搜尋條件的資料，你可以提供上一次的資料，本腳本會自動跳過已經抓取過的物件，然後在輸出的 CSV 檔案中將新的物件存在舊的前面：

```bash
python fetch_info.py --data-path cache/df_listings.csv
```

你可以同時追蹤多組搜尋條件，你只需要將預設 `df_listings.csv` 名稱改成各自條件的自訂名稱即可。

### 使用建議

個人推薦使用 LibreOffice Calc 開啓輸出的 CSV 檔案，一般會將 `desc` 欄位隱藏，利用 `mark` 欄位標記出自己感興趣的物件。**記得將修改結果回存到 CSV 檔案，這樣你的修改才會保留在下一次更新的結果中**。

![範例圖片](images/example-1.png)

## Acknowledgements

本組腳本參考了以下開源程式，謹此致謝：

1. [開放台灣民間租屋資料 (g0v/tw-rental-house-data)](https://github.com/g0v/tw-rental-house-data)
2. [591 租屋網 - 租屋資訊爬蟲 (AlanSyue/rent591data)](https://github.com/AlanSyue/rent591data)
