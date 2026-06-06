from ollama import Client

from typing_extensions import Literal, List, Dict, Any
from pydantic import BaseModel, Field

from PIL import Image
import io
from datetime import datetime
from bs4 import BeautifulSoup
import numpy as np
import requests
import os

client = Client(
    host="https://ollama.com",
    headers={'Authorization': 'Bearer ' + os.environ.get('OLLAMA_API_KEY')}
)

class Menu(BaseModel):
    main: str
    side_dishes: List[str] = Field(description="해당 메뉴와 제공된 반찬 등")
    allergens: Dict[str, List] = Field(description="하단참고, 알레르기 등 재료 안내사항", examples=[{"규동": ["소고기"], "미트볼": ["돼지고기", "닭고기"]}])
    calories: str
    price: str
    pork_free: bool

class LunchMenu(BaseModel):
    stall: Literal["든든", "푸짐", "우아"]
    menu: Menu

class Meal(BaseModel):
    meal_type: Literal["점심", "저녁"]
    menu: List[LunchMenu] | Menu

class DailyMenu(BaseModel):
    day: Literal["월", "화", "수", "목", "금"]
    date: datetime
    menu: List[Meal]

class WeeklyMenu(BaseModel):
    menu: List[DailyMenu]


def fetch_menu():
    headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    response = requests.get("https://khucoop.com/35", headers=headers)
    soup = BeautifulSoup(response.content)
    img_path = soup.find_all("img", "org_image")[0].get('src')
    response.close()

    img = requests.get(img_path)
    return img.content

def parse_menu():
    menu = io.BytesIO(fetch_menu())
    menu = Image.open(menu)
    cropped = menu.crop((120, 0, 1840, 345))
    menu = menu.crop((120, 1580, 1840, 4350))
    menu.paste(cropped, box=(0,0))
    menu = menu.convert('L')
    img_buffer = io.BytesIO()
    menu.save(img_buffer, format="PNG")
    img_bytes = img_buffer.getvalue()
    instruction = f"""You are an image parser that parses the weekly lunch (중식) and dinner (석식) menu(s) of a university cafeteria, including the accompanying side dishes (반찬). THe parsed image should follow the following JSON schema.
    JSON Schema:
    {WeeklyMenu.model_json_schema()}
    """

    message = [
        {"role": "system", "content": instruction},
        {"role": "user", "content": f"Parse the lunch (중식) and dinner (석식) sections of the following menu along with their allergens (main and side dishes), calories and price. Note that the current year is {datetime.today().year}.", "images": [img_bytes]}
    ]

    response = client.chat(
        model="qwen3-vl:235b-cloud",
        messages=message,
        options={"temperature": 0},
        format=WeeklyMenu.model_json_schema(),
    )

    weekly_menu = WeeklyMenu.model_validate_json(response.message.content.strip('```').replace("json", "").strip())
    weekly_menu = weekly_menu.model_dump(mode='json')
    for menu in weekly_menu['menu']:
        menu['date'] = menu['date'].split('T')[0]
    
    return weekly_menu

def format_sides(sides):
    return '\n'.join([f"- {side}" for side in sides])

def check_pork_free(allergens: dict, pork_free: bool):
    allergens = [ingredient for _menu in allergens.values() for ingredient in _menu]

    if pork_free and not "돼지고기" in set(allergens):
        return "돼지고기 無"
    else:
        return "돼지고기 有"

def format_menu_list(main, calories, side_dishes, pork_free, allergens, **kwargs):
    is_pork_free = check_pork_free(allergens=allergens, pork_free=pork_free)
    return f"""
{main} ({is_pork_free})
{format_sides(side_dishes)}
{calories}
""".strip()

def format_stall(stall, menu):
    menu = """
**{stall}**
""" + format_menu_list(**menu)
    menu = menu.format(stall=stall).strip()
    return menu

def format_lunch(per_stall_menus: list[dict]):
    return "\n\n".join([format_stall(**menu) for menu in per_stall_menus])

def format_daily(menu):
    lunch, dinner = menu['menu']
    lunch_menu = format_lunch(lunch['menu'])
    dinner_menu = format_menu_list(**dinner['menu'])
    daily_menu = """
**오늘 학식 메뉴 ({day} {date})**

**[점심]**
{lunch}

**[저녁]**
{dinner}
""".format(day=menu['day'], date=menu['date'].split('T')[0], lunch=lunch_menu, dinner=dinner_menu).strip()

    return daily_menu

def get_daily_menu(weekly_menu):
    return [format_daily(daily_menu) for daily_menu in weekly_menu['menu']]