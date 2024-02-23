import os
import random
from time import sleep, time
from datetime import datetime, timedelta
from tempfile import mkdtemp

from selenium import webdriver
from selenium_stealth import stealth
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

BAD_FINGRPRINT_CSS_SELECTOR = "#per-availability-main > div > div.per-availability-notification > div"
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
        "date_css_selector": "#per-availability-main > div > div.sarsa-box > div.per-availability-table-container > div.rec-grid-grid.detailed-availability-grid-new > div.per-availability-table > div:nth-child(2) > div:nth-child({cell_col}) > div > button",
        "date_xpath_selector": "/html/body/div[1]/div/div[4]/div/div/div[1]/div/div[4]/div[3]/div[2]/div[2]/div[2]/div[{cell_col}]/div/button",
        "min_date_col": 2,
    }
}


# make it compatible with AWS Lambda
def handler(event, context):
    email = os.environ.get("REC_EMAIL")
    password = os.environ.get("REC_PASSWORD")
    start_date = event.get("start_date")
    end_date = event.get("end_date")
    config_key = event.get("config")
    max_time = event.get("max_time", 500) # max time in seconds to run

    # try to find bookings for 5 minutes before giving up
    time_now = time()
    time_end = time_now + max_time
    while time_now < time_end:
        any_bookings = get_booking_started(
            start_date, end_date, email, password, config_key)
        if any_bookings:
            break
        time_now = time()


def get_booking_started(start_date, end_date, email, password, config_key=None):
    start_date = datetime.strptime(start_date, time_format)
    end_date = datetime.strptime(end_date, time_format)
    found_bookings = False

    user_agents = [
        # Add your list of user agents here
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
    ]
    # Create a new instance of the Firefox driver
    options = Options()

    # disable the AutomationControlled feature of Blink rendering engine
    options.add_argument('--disable-blink-features=AutomationControlled')

    # disable pop-up blocking
    options.add_argument('--disable-popup-blocking')
    # disable extensions
    options.add_argument('--disable-extensions')

    # disable sandbox mode
    options.add_argument('--no-sandbox')

    # disable shared memory usage
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument('--ignore-certificate-errors')
    options.add_argument("--disable-gpu")
    options.add_argument("--single-process")
    options.add_argument("--disable-dev-tools")
    options.add_argument("--no-zygote")
    options.add_argument(f"--user-data-dir={mkdtemp()}")
    options.add_argument(f"--data-path={mkdtemp()}")
    options.add_argument(f"--disk-cache-dir={mkdtemp()}")
    # user agent
    user_agent = random.choice(user_agents)
    options.add_argument(f'--user-agent={user_agent}')

    in_docker = os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False)
    kwargs = {"options": options}

    if in_docker:
        print("Running in Docker!")
        service = webdriver.ChromeService("/opt/chromedriver")
        options.binary_location = '/opt/chrome/chrome'
        kwargs["service"] = service

    driver = webdriver.Chrome(**kwargs)

    # Change the property value of the navigator for webdriver to undefined
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    stealth(
        driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )

    # login
    driver.get("https://www.recreation.gov/")
    login_button = driver.find_element(By.ID, "ga-global-nav-log-in-link")
    login_button.click()

    email_field = driver.find_element(By.ID, "email")
    email_field.clear()
    email_field.send_keys(email)
    sleep(random.expovariate(1. / 0.5))
    password_field = driver.find_element(By.ID, "rec-acct-sign-in-password")
    password_field.clear()
    password_field.send_keys(password)

    login_button = driver.find_element(By.CLASS_NAME, "rec-acct-sign-in-btn")
    sleep(random.expovariate(1. / 0.5))
    login_button.click()

    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "rec-sr-content"))
        )
        sleep(2 + random.expovariate(1. / 0.5))
    except:
        print("Timed out waiting for home page to load")
    # Open the webpage with the table
    if config_key is None:
        config = list(CONFIGS.values())[0]
    else:
        config = CONFIGS[config_key]

    # go through the dates to find availability
    current_date = start_date
    while current_date <= end_date:
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
                    print("Timed out waiting for calendar page to load.")
                    continue
            # Find the cell for the reservation date
            if use_selector:
                cell = driver.find_element(By.CSS_SELECTOR, cell_selector)
            else:
                cell = driver.find_element(By.XPATH, cell_xpath)

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
            book_button = driver.find_element(By.CSS_SELECTOR, "#per-availability-main > div > div.sarsa-box > div:nth-child(4) > div > div > div > button")
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
                found_bookings = True
            except:
                print("Timed out waiting for booking page to load.")
                error_field_text = None
                try:
                    error_field = driver.find_element(By.CSS_SELECTOR, BAD_FINGRPRINT_CSS_SELECTOR)
                    error_field_text = error_field.text
                except:
                    pass

                if error_field_text:
                    print(f"Error: {error_field_text}")
                else:
                    print(f"Not a bad fingerprint error, something else")
                # unselect date
                cell.click()
                continue

        current_date = current_date + timedelta(days=10)

        # GO TO THE NEXT PAGE TWICE TO GET FRESH IDS
        next_page_css_selector = "#per-availability-main > div > div.sarsa-box > div.sarsa-stack.md > div > div:nth-child(2) > div > div > button.sarsa-button.ml-1.mr-2.sarsa-button-link.sarsa-button-xs"

        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, next_page_css_selector))
            )
        except:
            print("Timed out waiting for next page to load.")
            break

        next_page = driver.find_element(By.CSS_SELECTOR, next_page_css_selector)
        next_page.click()
        sleep(0.2 + random.expovariate(1. / 0.5))
        next_page.click()
        sleep(0.1 + random.expovariate(1. / 0.5))
    # Close the browser
    driver.quit()

    # return whether bookings were found
    return found_bookings


if __name__ == "__main__":
    email = os.environ.get("REC_EMAIL")
    password = os.environ.get("REC_PASSWORD")
    config_key = "dinosaur"
    get_booking_started("2024-03-01", "2024-03-05", email, password, config_key)
