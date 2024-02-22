import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from time import sleep
from datetime import datetime, timedelta

time_format = "%Y-%m-%d"
jump_date_format = "%m/%d/%Y"
CONFIGS = {
    "salmon": {
        "permit_id": "234622",
        "date_css_selector": "#per-availability-main > div > div.sarsa-box > div.per-availability-table-container > div.rec-grid-grid.detailed-availability-grid-new > div:nth-child(2) > div > div:nth-child({cell_col}) > div > button",
        "date_xpath_selector": "/html/body/div[1]/div/div[3]/div/div/div[1]/div/div[4]/div[3]/div[2]/div[2]/div/div[{cell_col}]/div/button",
        "min_date_col": 2,
    },
    "desolation": {
        "permit_id": "233393",
        "date_css_selector": "#per-availability-main > div > div.sarsa-box > div.per-availability-table-container > div.rec-grid-grid.detailed-availability-grid-new.has-area-data > div:nth-child(2) > div > div:nth-child({cell_col}) > div > button",
        "date_xpath_selector": "/html/body/div[1]/div/div[3]/div/div/div[1]/div/div[4]/div[3]/div[2]/div[2]/div/div[{cell_col}]/div/button",
        "min_date_col": 3,
    },
    "dinosaur": {
        "permit_id": "250014",
    }
}


def get_booking_started(start_date, end_date, email, password, configs=None):
    start_date = datetime.strptime(start_date, time_format)
    end_date = datetime.strptime(end_date, time_format)
    # Create a new instance of the Firefox driver
    driver = webdriver.Chrome()

    # login
    driver.get("https://www.recreation.gov/")
    login_button = driver.find_element(By.ID, "ga-global-nav-log-in-link")
    login_button.click()

    email_field = driver.find_element(By.ID, "email")
    email_field.clear()
    email_field.send_keys(email)

    password_field = driver.find_element(By.ID, "rec-acct-sign-in-password")
    password_field.clear()
    password_field.send_keys(password)

    login_button = driver.find_element(By.CLASS_NAME, "rec-acct-sign-in-btn")

    login_button.click()

    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "rec-sr-content"))
        )
        sleep(2)
    except:
        print("Timed out waiting for page to load.")
    # Open the webpage with the table
    if configs is None:
        configs = list(CONFIGS.values())
    else:
        configs = [CONFIGS[config] for config in configs]
    for config in configs:
        current_date = start_date
        while current_date <= end_date:
            driver.delete_all_cookies()
            driver.get(f"https://www.recreation.gov/permits/{config['permit_id']}/registration/detailed-availability?date={current_date.strftime(time_format)}")

            # loop through cell columns
            min_cell_col = config["min_date_col"]
            max_cell_col = min_cell_col + 10
            date_diff = end_date - current_date

            if date_diff.days < 10:
                max_cell_col = date_diff.days + min_cell_col

            # cells = driver.find_elements(By.CLASS_NAME, "rec-availability-date"))
            for cell_col in range(min_cell_col, max_cell_col):
                cell_selector = config["date_css_selector"].format(cell_col=cell_col)
                cell_xpath = config["date_xpath_selector"].format(cell_col=cell_col)
                use_selector = False
                try:
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, cell_selector))
                    )
                    use_selector = True
                except:
                    try:
                        WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, cell_xpath))
                        )
                    except:
                        print("Timed out waiting for page to load.")
                        continue
                # Find the cell for the reservation date
                if use_selector:
                    cell = driver.find_element(By.CSS_SELECTOR, cell_selector)
                else:
                    cell = driver.find_element(By.XPATH, cell_xpath)
                # /html/body/div[1]/div/div[3]/div/div/div[1]/div/div[4]/div[3]/div[2]/div[2]/div[1]/div[11]/div/button
                # /html/body/div[1]/div/div[3]/div/div/div[1]/div/div[4]/div[3]/div[2]/div[2]/div[1]/div[2]/div/button
                # "/html/body/div[1]/div/div[4]/div/div/div[1]/div/div[4]/div[3]/div[2]/div[2]/div[1]/div[6]/div/button"
                # "/html/body/div[1]/div/div[4]/div/div/div[1]/div/div[4]/div[3]/div[2]/div[2]/div[2]/div[6]/div/button"
                # Get the initial state of the cell (if it's selected or not)
                initial_state = cell.get_attribute("aria-label")
                if "available" not in initial_state.lower() or "unavailable" in initial_state.lower():
                    continue

                # Click the cell to simulate selecting it
                cell.click()

                # Get the updated state of the cell after clicking
                updated_state = cell.get_attribute("aria-label")

                # Check if the state has changed as expected
                if "selected" not in updated_state.lower():
                    continue

                # try to click the "Book" button
                book_button = driver.find_element(By.XPATH, "/html/body/div[1]/div/div[3]/div/div/div[1]/div/div[4]/div[4]/div/div/div/button")
                # could not continue with booking
                if "disabled" in book_button.get_attribute("class").lower():
                    continue
                # add item to booking
                book_button.click()
                try:
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.ID, "first_name"))
                    )
                    driver.back()
                except:
                    print("Timed out waiting for page to load.")
                    continue

            # jump field will be the death of me
            # clear jump-date field
            # jump_date_field = driver.find_element(By.ID, "jump-date")
            # jump_date_field.clear()
            current_date = current_date + timedelta(days=10)
            # driver.execute_script(
            #     "arguments[0].value = arguments[1];",
            #     jump_date_field,
            #     current_date.strftime(jump_date_format)
            # )
            # CHANGING TABS INSTEAD
            # driver.execute_script("window.open('about:blank', '_blank');")
            # driver.close()
            # driver.switch_to.window(driver.window_handles[-1])
            ### SHUTTING DOWN THE DRIVER
            #driver.quit()
            #driver = webdriver.Chrome()
            # GO TO THE NEXT PAGE TWICE TO GET FRESH IDS
            next_page = driver.find_element(By.CSS_SELECTOR, "#per-availability-main > div > div.sarsa-box > div.sarsa-stack.md > div > div:nth-child(2) > div > div > button.sarsa-button.ml-1.mr-2.sarsa-button-link.sarsa-button-xs")
            next_page.click()
            sleep(0.3)
            next_page.click()
            sleep(0.3)
    # Close the browser
    driver.quit()


if __name__ == "__main__":
    email = os.environ.get("REC_EMAIL")
    password = os.environ.get("REC_PASSWORD")
    configs = ["desolation"]
    get_booking_started("2024-03-01", "2024-03-11", email, password, configs)