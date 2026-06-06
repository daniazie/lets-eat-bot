from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError
from apscheduler.schedulers.background import BackgroundScheduler

import datetime
import logging
import os

from utils.menu_parser import parse_menu, get_daily_menu

logger = logging.getLogger(__name__)

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
channel_id = os.environ['CHANNEL_ID']

def schedule_message(daily_menu, scheduled_date, scheduled_time):
    schedule = datetime.datetime.combine(scheduled_date, scheduled_time).strftime("%s")
    try:
        result = app.client.chat_scheduleMessage(
            channel=channel_id,
            post_at=schedule,
            markdown_text=daily_menu
        )
        logger.info(result)
    except SlackApiError as e:
        logger.error("Error scheduling message: {}".format(e))
    

def post_menu():
    logger.info("Parsing menu...")
    weekly_menu = parse_menu()
    scheduled_time = datetime.time(10, 0)
    schedule_dates = [datetime.datetime.fromisoformat(menu['date']) for menu in weekly_menu['menu']]
    daily_menus = get_daily_menu(weekly_menu)

    for daily_menu, date in zip(daily_menus, schedule_dates):
        schedule_message(daily_menu, date, scheduled_time)

if __name__ == "__main__":
    logger.info("Loading bot...")
    scheduler = BackgroundScheduler()
    job = scheduler.add_job(post_menu, 'cron', day_of_week='mon', hour=9, minute=30)
    scheduler.start()

    handler = SocketModeHandler(app, app_token=os.environ.get("SLACK_APP_TOKEN"), logger=logger)
    handler.start()