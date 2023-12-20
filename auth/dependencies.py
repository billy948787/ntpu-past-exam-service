import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import HTTPException
import json
import os

load_dotenv()



def get_lms_user_info(username: str, password: str):
    response = requests.post(
        "https://cof.ntpu.edu.tw/pls/pm/stud_system.login",
        data={
            "stud_num": username,
            "passwd": password,
            "x": "109",
            "y": "15",
        },
        timeout=10,
    )
    cookies = response.cookies
    soup = BeautifulSoup(response.text, "html.parser")
    if soup.find("h3"):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    timestamp = (
        soup.find("body")
        .get("onload")
        .split("window.open('../univer/query_all_course.login2?date1=")[1]
        .split("','_top')")[0]
    )

    user_info_link = f"https://cof.ntpu.edu.tw/pls/univer/query_all_course.judge?func=10&date1={timestamp}"

    user_info_page = requests.get(user_info_link, cookies=cookies, timeout=10)
    user_info_soup = BeautifulSoup(user_info_page.text, "html.parser")

    readable_name = user_info_soup.find(text="(選課說明：").parent.find_all("span")[3].text
    department = user_info_soup.find(text="(選課說明：").parent.find_all("span")[1].text

    contact_link = f"https://cof.ntpu.edu.tw/pls/univer/query_all_course.judge?func=18&date1={timestamp}"
    contact_page = requests.get(contact_link, cookies=cookies, timeout=10)
    contact_soup = BeautifulSoup(contact_page.text, "html.parser")

    email = contact_soup.find("input", {"type": "email"}).get("value")

    return {
        "readable_name": readable_name,
        "department": department,
        "email": email,
    }


def exchange_token_with_google(code: str, redirect_uri: str):
    try:
        response = requests.post('https://oauth2.googleapis.com/token', data={
            'client_id': os.getenv('GOOGLE_SERVICE_CLIENT_ID'),
            'client_secret': os.getenv('GOOGLE_SERVICE_SERCET'),
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        })

        data = json.loads(response.text)
        google_access_token = data['access_token']

        info_url = 'https://www.googleapis.com/oauth2/v1/userinfo'
        info_response = requests.get(info_url, headers={
            'Authorization': f'Bearer {google_access_token}'
        })
        user_data = json.loads(info_response.text)
        if user_data["hd"] != 'gm.ntpu.edu.tw':
            raise HTTPException(status_code=403)
        return user_data
    except KeyError:
        raise HTTPException(status_code=403)
