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


def get_number_of_pages_and_items(html, items_per_page=30):
    soup = make_soup(html)
    text_with_number = soup.find('span', class_='js-place-count').get_text()
    number_of_items = int(text_with_number.split()[0])
    return math.ceil(number_of_items/items_per_page), number_of_items


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

def get_blizzard_link(html):
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


def main():
    user_agents = load_user_agents()
    proxies = load_proxies()
    loaded_page = load_pickle(config.PAGE_PICKLE)
    page = -1 if loaded_page is None else loaded_page
    active_chars_p = picklize('active_chars', page)
    loaded_active_chars = load_pickle(active_chars_p)
    active_chars = Vividict() if loaded_active_chars is None else loaded_active_chars
    print('active_chars length', len(active_chars))
    url = config.EU_SEARCH_URL
    while len(active_chars) < 1000:
        print('#'*10)
        print('len',len(active_chars))
        print('starting to parse page', page)
        page_w_chars_html = try_get_html_wo_proxy(url, page=page, ua=random.choice(user_agents), proxy_item=random.choice(proxies))
        one_page_chars = get_one_page_chars(page_w_chars_html)
        for char in one_page_chars:
            print(char[0])
            char_url = config.DOMAIN + char[1]
            char_html = try_get_html_wo_proxy(char_url, ua=random.choice(user_agents), proxy_item=None)
            blizzard_link = get_blizzard_link(char_html)
            if active_chars[blizzard_link]:
                print('already_here')
                continue
            proxy = None
            while True:
                try:
                    blizzard_html = get_html(blizzard_link, ua=random.choice(user_agents), proxy_item=proxy)
                    break
                except:
                    proxy = random.choice(proxies)
                    print('trying another proxy', proxy)
            active = check_if_active(get_html(blizzard_link))
            print(active, blizzard_link) 
            if active:
                name, server = active
                active_chars[blizzard_link]['rank'] = char[0]
                active_chars[blizzard_link]['points'] = char[2]
                active_chars[blizzard_link]['name'] = name
                active_chars[blizzard_link]['server'] = server
        save_pickle(active_chars, picklize('active_chars', page))
        save_pickle(page, config.PAGE_PICKLE)
        break
        page += 1
    print(active_chars)
    print(len(active_chars))







def ma22in():
    loaded_countries_dict = load_pickle(config.COUNTRIES_DICT_PICKLE)
    if loaded_countries_dict is None:
        print('getting countries_dict')
        countries_dict = get_all_city_links(get_html(config.ALL_CITIES_LINK),
                                            config.NEEDED_COUNTRIES)
        save_pickle(countries_dict, config.COUNTRIES_DICT_PICKLE)
    else:
        countries_dict = loaded_countries_dict
        print('loaded countries_dict')
    
    city_dict_list = []
    for country in countries_dict:
        if country == 'Украина':# testing
            print('parsing', country)
            for city in countries_dict[country]:
#                if city == 'Одесса':# testing
                print('parsing', city)
                url = countries_dict[country][city]
                number_of_pages, number_of_items = get_number_of_pages_and_items(get_html(url, config.PLACE_TYPE))
                print(number_of_items, 'places in', city)
                city_pickle_name = picklize(country, city)
                loaded_city = load_pickle(city_pickle_name)
                if loaded_city is None:
                    city_dict = Vividict()                   
                    for page in range(1, number_of_pages + 1):
                        one_page_items = get_places_list(fetch_post_html(url, config.PLACE_TYPE, page))
                        for item in one_page_items:
                            city_dict[item[0]]['link'] = item[1]
#                               print(city_dict[item[0]]['link'])
                            city_dict[item[0]]['short_name'] = item[0]
                            place_info = get_detailed_info(get_html(item[1]))
                            city_dict[item[0]]['full_name'] = place_info[0]
                            city_dict[item[0]]['city'] = place_info[1]
                            city_dict[item[0]]['street'] = place_info[2]
                            city_dict[item[0]]['home'] = place_info[3]
                            city_dict[item[0]]['district'] = place_info[4]
                            city_dict[item[0]]['metro'] = place_info[5]
                            city_dict[item[0]]['website'] = place_info[6]
                            city_dict[item[0]]['social'] = place_info[7]
                            city_dict[item[0]]['phone'] = place_info[8]
                            city_dict[item[0]]['issue'] = place_info[9]
                            city_dict[item[0]]['country'] = country
                        show_progress(page, number_of_pages)
                    
                    save_pickle(city_dict, city_pickle_name)
                else:
                    city_dict = loaded_city

#                    pprint.pprint(city_dict)
                    city_dict_list.append(city_dict)
#    print(city_dict_list)
    output_info_to_xlsx(city_dict_list, 'result.xlsx')

    

if __name__ == '__main__':
    main()
