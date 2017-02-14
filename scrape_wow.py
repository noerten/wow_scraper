import logging
import math
import os
import pickle
import pprint
import random
import sys
import time
import traceback
import collections
import urllib.parse
import unicodedata
import re
import concurrent.futures

from openpyxl import Workbook

import requests
from bs4 import BeautifulSoup

from pickle_io import load_pickle
from pickle_io import save_pickle
from pickle_io import picklize

from scraping_tools import load_user_agents
from scraping_tools import load_proxies

import config


def show_progress(current, total, decimals=2):
    number = current / total*100
    print('{0:,.{1}f}%'.format(number, decimals))

def make_soup(html):
    return BeautifulSoup(html, 'html.parser')


def get_html(url, page=None, ua=None, proxy_item=None):
    if proxy_item:
        proxy = {"http": proxy_item}
    else:
        proxy = None
    post_data = {'ajax':1}
    if ua:
        headers = {
            "Connection" : "close",  # another way to cover tracks
            "User-Agent" : ua}
    else:
        headers = None
    if page:
        return requests.post(url+str(page), headers=headers, data = post_data, proxies=proxy).text
    else:
        return requests.get(url, headers=headers, proxies=proxy, timeout=5).text


def output_info_to_xlsx(info, filepath):
    header = ['Краткое название', 'Полное название', 'Страна', 'Город', 'Улица',
              'Дом', 'Район', 'Метро', 'Вебсайт', 'Соцсеть', 'Телефон', 'Проблема']
    wbook = Workbook()
    wsheet = wbook.active
    wsheet.append(header)
    for city_dict in info:
        for place in sorted(city_dict.keys()):
            row = (city_dict[place]['short_name'], city_dict[place]['full_name'], city_dict[place]['country'],
                   city_dict[place]['city'], city_dict[place]['street'], city_dict[place]['home'], city_dict[place]['district'],
                   city_dict[place]['metro'], city_dict[place]['website'], city_dict[place]['social'], city_dict[place]['phone'],
                   city_dict[place]['issue'])
            wsheet.append(row)
    wbook.save(filepath)

class Vividict(dict):
    def __missing__(self, key):
        value = self[key] = type(self)()
        return value

def get_one_page_chars(page_html):
    soup = make_soup(page_html)
    chars = []
    for span_rank in soup.find_all('span', class_='rank'):
        rank = span_rank.get_text()
        link = span_rank.parent.parent.a.get('href')
        points = span_rank.parent.parent.find('td', class_='center').get_text()
        chars.append([rank, link, points])
    return chars

def extract_blizzard_link(html):
    soup = make_soup(html)
    return soup.find('a', class_='armoryLink').get('href')


def check_if_active(html):
    soup = make_soup(html)
    level = int(
        soup.find('div',
                  class_='profile-info').find(class_='level').get_text())
    if level < 110:
        return False
    item_level = int(soup.find(id='summary-averageilvl-best').get_text())
    if item_level <= 870:
        return False
    activity = soup.find('ul', class_='activity-feed').get_text() 
    if 'hour' or '1 day' or '2 day' or '3 day' or '4 day' or '5 day' in activity:
        name = soup.find('div', class_='name').get_text().strip()
        server = soup.find(id='profile-info-realm').get_text().strip()
        return name, server
    
def try_get_html_wo_proxy(url, ua=None, proxy_item = None, page=None):
    try:
        return get_html(url, page=page, ua=ua)   
    except:
        return get_html(url, page=page, ua=ua, proxy_item=proxy_item)

def init_page():
    loaded_page = load_pickle(config.PAGE_PICKLE)
    return -1 if loaded_page is None else loaded_page

def init_chars(page):
    active_chars_p = picklize('active_chars', page)
    loaded_active_chars = load_pickle(active_chars_p)
    return Vividict() if loaded_active_chars is None else loaded_active_chars


def get_blizzard_link(char_link, user_agents):
    char_url = config.DOMAIN + char_link
    char_html = try_get_html_wo_proxy(char_url, ua=random.choice(user_agents), proxy_item=None)
    return extract_blizzard_link(char_html)


def get_char_info(blizzard_link, user_agents, proxy):
    while True:
        try:
            blizzard_html = get_html(blizzard_link, ua=random.choice(user_agents), proxy_item=proxy)
            break
        except:
            proxy = random.choice(proxies)
            print('trying another proxy', proxy)
    return check_if_active(get_html(blizzard_link))


def scrape_char(active_chars, char, user_agents, proxy):
    print(char[0])
    blizzard_link = get_blizzard_link(char[1], user_agents)
    if active_chars[blizzard_link]:
        print('already_here')
        return
    char_info = get_char_info(blizzard_link, user_agents, proxy)
    if char_info:
        return blizzard_link, char[0], char[2], char_info[0], char_info[1]

    

def main():
    user_agents = load_user_agents()
    proxies = load_proxies()
    page = init_page()
    active_chars = init_chars(page)
    print('active_chars length', len(active_chars))
    url = config.EU_SEARCH_URL
    while len(active_chars) < 1000:
        print('#'*10)
        print('len',len(active_chars))
        print('starting to parse page', page)
        page_w_chars_html = try_get_html_wo_proxy(url, page=page, ua=random.choice(user_agents), proxy_item=random.choice(proxies))
        one_page_chars = get_one_page_chars(page_w_chars_html)
        proxy = None
        for char in one_page_chars:
            char_info = scrape_char(active_chars, char, user_agents, proxy)
            if char_info:    
                active_chars[char_info[0]]['rank'] = char_info[1]
                active_chars[char_info[0]]['points'] = char_info[2]
                active_chars[char_info[0]]['name'] = char_info[3]
                active_chars[char_info[0]]['server'] = char_info[4]
                print(active_chars[char_info[0]])
        
        save_pickle(active_chars, picklize('active_chars', page))
        save_pickle(page, config.PAGE_PICKLE)
        break
        page += 1
    print(active_chars)
    print(len(active_chars))
    

if __name__ == '__main__':
    main()
