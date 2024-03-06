import os
import boto3
import random
from time import sleep, time
from datetime import datetime, timedelta
from tempfile import mkdtemp

import pytz
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
        "dates": "2024-7-1/2/3/4"
    },
    "desolation": {
        "permit_id": "233393",
        "date_css_selector": "#per-availability-main > div > div.sarsa-box > div.per-availability-table-container > div.rec-grid-grid.detailed-availability-grid-new.has-area-data > div:nth-child(2) > div > div:nth-child({cell_col}) > div > button",
        "date_xpath_selector": "/html/body/div[1]/div/div[3]/div/div/div[1]/div/div[4]/div[3]/div[2]/div[2]/div/div[{cell_col}]/div/button",
        "min_date_col": 3,
        "dates": "2024-7-1/2/3/4"
    },
    "dinosaur": {
        "permit_id": "250014",
        "date_css_selector": "#per-availability-main > div > div.sarsa-box > div.per-availability-table-container > div.rec-grid-grid.detailed-availability-grid-new > div.per-availability-table > div:nth-child(2) > div:nth-child({cell_col}) > div > button",
        "date_xpath_selector": "/html/body/div[1]/div/div[4]/div/div/div[1]/div/div[4]/div[3]/div[2]/div[2]/div[2]/div[{cell_col}]/div/button",
        "min_date_col": 2,
        "dates": "2024-06-23-24-25",
    },
    "salmon-middle-fork": "2024-06-23/24/25",
}

BUCKET_NAME = "debucketforpng"


# make it compatible with AWS Lambda
def handler(event, context):
    email = os.environ.get("REC_EMAIL")
    password = os.environ.get("REC_PASSWORD")
    start_date = event.get("start_date")
    end_date = event.get("end_date")
    config_key = event.get("config")
    max_time = event.get("max_time", 500)  # max time in seconds to run
    trigger_time = event.get("trigger_time", "08:00:00")  # trigger time in HH:MM:SS
    trigger_time_zone = event.get("trigger_time_zone", "America/Denver")  # trigger time zone

    # try to find bookings for 5 minutes before giving up
    time_now = time()
    time_end = time_now + max_time

    # tracker for early exits
    early_exits = 0
    EARLY_EXIT_THRESHOLD = 3
    while time_now < time_end:
        if early_exits >= EARLY_EXIT_THRESHOLD:
            print("Too many early exits, sleeping for a few seconds")
            sleep(30)
            early_exits = 0
        function_max_time = time_end - time_now
        any_bookings, early_exit = get_booking_started(
            start_date,
            end_date,
            email,
            password,
            config_key,
            function_max_time,
            trigger_time,
            trigger_time_zone,
        )
        if early_exit:
            early_exits += 1
        if any_bookings:
            break
        time_now = time()


def get_booking_started(
    start_date,
    end_date,
    email,
    password,
    config_key=None,
    max_time=500,
    trigger_time="08:00:00",
    trigger_time_zone="America/Denver",
):
    # keep track of timeouts to see if we need to restart the browser
    TIMEOUT_LIMIT = 5
    num_timeouts = 0

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
    # disable cache (did not help with 429)
    # options.add_argument('--disable-cache')

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
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "ga-global-nav-log-in-link"))
        )
    except:
        print("Timed out waiting for login link to load")
        s3 = boto3.client('s3')
        fname = datetime.now().strftime("%Y%m%d%H%M%S") + "_login_link_screenshot.png"
        driver.save_screenshot("/tmp/" + fname)
        s3.upload_file("/tmp/" + fname, BUCKET_NAME, fname)
        driver.quit()
        return False, True

    login_button = driver.find_element(By.ID, "ga-global-nav-log-in-link")
    login_button.click()

    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "email"))
        )
    except:
        print("Timed out waiting for login page to load")
        s3 = boto3.client('s3')
        fname = datetime.now().strftime("%Y%m%d%H%M%S") + "_login_page_screenshot.png"
        driver.save_screenshot("/tmp/" + fname)
        s3.upload_file("/tmp/" + fname, BUCKET_NAME, fname)
        driver.quit()
        return False, True

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
        s3 = boto3.client('s3')
        fname = datetime.now().strftime("%Y%m%d%H%M%S") + "_home_page_screenshot.png"
        driver.save_screenshot( "/tmp/" + fname)
        s3.upload_file("/tmp/" + fname, BUCKET_NAME, fname)
        num_timeouts += 1
    # Open the webpage with the table
    if config_key is None:
        config = list(CONFIGS.values())[0]
    else:
        config = CONFIGS[config_key]

    # go through the dates to find availability
    current_date = start_date
    # number of clicks it took to get to the current date
    num_clicks = 0

    # intialize early exit tracker
    early_exit = False

    trigger_time_dt = datetime.strptime(trigger_time, "%H:%M:%S")
    target_tz = pytz.timezone(trigger_time_zone)

    # Get the current date in Target Time
    current_date_target = datetime.now(target_tz).date()

    # Combine the current date with the target time to create a datetime object
    target_datetime = datetime.combine(current_date_target, trigger_time_dt.time())

    # Localize the target datetime to Time Time
    target_datetime_local = target_tz.localize(target_datetime)

    # Get the current time in Target Time
    current_time_target = datetime.now(target_tz)
    print(f"Current time in Target Time: {current_time_target}")
    checkin_time = current_time_target + timedelta(seconds=15)
    while current_time_target < target_datetime_local:
        # Get the current time in Target Time
        current_time_target = datetime.now(target_tz)
        if checkin_time >= current_time_target:
            print("Still waiting for the trigger time")
            print(f"Current time in Target Time: {current_time_target}")

        sleep(0.1)

    print("Starting the search!")
    time_now = time()
    time_end = time_now + max_time
    while time_now < time_end:
        if found_bookings:
            break

        if num_timeouts >= TIMEOUT_LIMIT:
            print("Too many timeouts, restarting the browser")
            early_exit = True
            break

        if num_clicks > 0:
            print("Went through all the dates, going back to the first date")
            # sleep a bit to reduce load on server
            sleep(15 + random.expovariate(1. / 5))
            prev_page_selector = "#per-availability-main > div > div.sarsa-box > div.sarsa-stack.md > div > div:nth-child(2) > div > div > button:nth-child(1)"
            try:
                prev_page = driver.find_element(By.CSS_SELECTOR, prev_page_selector)
            except:
                print("Could not find the previous page button, restarting the browser")
                early_exit = True
                break
            for _ in range(num_clicks):
                try:
                    prev_page.click()
                    sleep(0.1 + random.expovariate(1. / 0.2))
                except:
                    print("Could not click the previous page button, restarting the browser")
                    early_exit = True
                    break
            # reset the number of clicks
            num_clicks = 0
        # reset the current date
        current_date = start_date

        # update the time
        time_now = time()
        # go outwards from center
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
                if num_timeouts >= TIMEOUT_LIMIT:
                    early_exit = True
                    break

                cell_selector = config["date_css_selector"].format(cell_col=cell_col)
                cell_xpath = config["date_xpath_selector"].format(cell_col=cell_col)
                use_selector = False
                try:
                    WebDriverWait(driver, 20).until(
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
                        s3 = boto3.client('s3')
                        fname = datetime.now().strftime("%Y%m%d%H%M%S") + "_calendar_screenshot.png"
                        driver.save_screenshot("/tmp/" + fname)
                        s3.upload_file("/tmp/" + fname, BUCKET_NAME, fname)

                        num_timeouts += 1
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
                    s3 = boto3.client('s3')
                    fname = datetime.now().strftime("%Y%m%d%H%M%S") + "_booking_page_screenshot.png"
                    driver.save_screenshot("/tmp/" + fname)
                    s3.upload_file("/tmp/" + fname, BUCKET_NAME, fname)
                    error_field_text = None
                    try:
                        error_field = driver.find_element(By.CSS_SELECTOR, BAD_FINGRPRINT_CSS_SELECTOR)
                        error_field_text = error_field.text
                    except:
                        pass

                    if error_field_text:
                        print(f"Error: {error_field_text}")
                        if ("You are allowed to hold 1 permit(s) at a time." in error_field_text
                                or "You must really like this location!" in error_field_text):
                            found_bookings = True
                            break
                    else:
                        num_timeouts += 1
                        print("Not a bad fingerprint error, something else")
                    # unselect date
                    cell.click()
                    continue

            # you can see ten days in the detailed availability page
            # so we need to jump to the next 10 dates
            current_date = current_date + timedelta(days=10)

            # don't need to go to next page if date range is less than 10 days
            if end_date - start_date < timedelta(days=10):
                continue
            # GO TO THE NEXT PAGE TWICE TO GET FRESH IDS
            next_page_css_selector = "#per-availability-main > div > div.sarsa-box > div.sarsa-stack.md > div > div:nth-child(2) > div > div > button.sarsa-button.ml-1.mr-2.sarsa-button-link.sarsa-button-xs"

            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, next_page_css_selector))
                )
            except:
                print("Timed out waiting for next page to load.")
                s3 = boto3.client('s3')
                fname = datetime.now().strftime("%Y%m%d%H%M%S") + "_next_page_screenshot.png"
                driver.save_screenshot("/tmp/" + fname)
                s3.upload_file("/tmp/" + fname, BUCKET_NAME, fname)
                num_timeouts += 1
                break

            next_page = driver.find_element(By.CSS_SELECTOR, next_page_css_selector)
            next_page.click()
            num_clicks += 1
            sleep(0.2 + random.expovariate(1. / 0.5))
            next_page.click()
            num_clicks += 1
            sleep(0.1 + random.expovariate(1. / 0.5))

    # Close the browser
    driver.quit()

    # return whether bookings were found
    return found_bookings, early_exit


if __name__ == "__main__":
    email = os.environ.get("REC_EMAIL")
    password = os.environ.get("REC_PASSWORD")
    config_key = "desolation"
    get_booking_started(
        "2024-03-08",
        "2024-03-16",
        email,
        password,
        config_key,
        trigger_time="01:26:00",
        trigger_time_zone="America/Denver",
        )
