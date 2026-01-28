import requests
import os
import re
import time
from bs4 import BeautifulSoup
import urllib.parse
from playwright.sync_api import sync_playwright
from loguru import logger
from .shared import *


logger.add("log.log", rotation="1 MB", retention="30 days", compression="zip")

download_dir = 'download/e_hentai'
invalid_chars = r'[<>:"/\\|?*]'  

eh_category_to_bin={
    'misc':1,
    'doujinshi':2,
    'manga':4,
    'artist_cg':8,
    'game_cg':16,
    'image_set':32,
    'cosplay':64,
    'asian_porn':128,
    'non-h':256,
    'western':512
}

def find_all_page_urls(html):
    '''
    given a page in the artwork, find all pages of this artwork
    e.g. https://e-hentai.org/g/xxx/yyy/?p=1 find ?p=2,?p=3...
    '''
    urls = set()
    soup = BeautifulSoup(html, 'html.parser')
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if href.startswith('https://e-hentai.org/g/'):
            urls.add(href)
    return sorted(list(urls))

def find_all_img_urls(html):
    '''
    given a page in the artwork, find all imgs links on this page
    '''
    url_to_img_idx = dict()
    soup = BeautifulSoup(html, 'html.parser')
    for a_tag in soup.find_all('a', href=True):
        url = a_tag['href']
        if url.startswith('https://e-hentai.org/s/'):
            img_idx = int(url.split('/')[-1].split('-')[-1])
            url_to_img_idx[url] = img_idx
    
    #sort urls by img_idx
    urls = [url for url, _ in sorted(url_to_img_idx.items(), key=lambda item: item[1])]

    return urls

def download_imgs_from_img_urls(urls, folder_name, ext):
    #count idx of imgs
    idx = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for url in urls:
            save_dir=f'{download_dir}/{folder_name}/{idx}.{ext}'
            
            try:
                if not os.path.isfile(save_dir):
                    print(f"Downloading: {url} -> {save_dir}")
                    page.goto(url)
                    img_url = page.get_attribute('#img', 'src')
                    response = requests.get(img_url)
                    response.raise_for_status()

                    os.makedirs(f'{download_dir}/{folder_name}', exist_ok=True)
                    with open(save_dir, "wb") as f:
                        f.write(response.content)
                    time.sleep(1)
                else:
                    print(f'{save_dir} already exist, skipping it')

            except Exception as error:
                logger.warning(f"Timeout when downloading: {url}, skipping it, error: {error}")
                continue
            
            finally:
                idx += 1

        browser.close()
        


def download_one_artwork(url, folder_name, ext):
    assert ext in ["jpg", "jpeg", "png", "gif", "webp", "bmp"]

    img_urls = []

    page = requests.get(url, timeout=10).text
    all_page_urls = find_all_page_urls(page)

    for page_url in all_page_urls:
        page = requests.get(page_url, timeout=10).text
        img_urls += find_all_img_urls(page)

    download_imgs_from_img_urls(img_urls, folder_name, 'png')



def eh_download(search_text, ext='png', avoid_categories:set =set(), f_srdd=0, f_spf=0, f_spt=9999):
    '''
    download all artworks
    avoid_categories: a list of unwanted categories in eh_category_to_bin
    f_srdd: only download imgs with rating higher than f_srdd
    f_spf: only download imgs with f_spf or more pages
    f_spt: only download imgs with f_spf or less pages (f_spt-f_spf must >=10)
    '''

    assert f_spt-f_spf>=10, 'f_spt-f_spf must >=10'
    assert avoid_categories.issubset(set(eh_category_to_bin.keys())), f'avoid_categories must be in {eh_category_to_bin.keys()}'
    f_cats = 0+sum([eh_category_to_bin[cat] for cat in avoid_categories])
    query_dict = {'f_srdd':f_srdd,
             'f_spf':f_spf,
             'f_spt':f_spt,
             'f_cats': f_cats,
             'f_search':search_text,
             'next':''}
    query = urllib.parse.urlencode(query_dict)

    a_tags = {1} #dummy
    while a_tags:
        artwork_title_to_url = dict()
        last_artwork_url = ''

        url = f'https://e-hentai.org/?advsearch=1&{query}'
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        page = response.text
    
        if 'This IP address has been temporarily banned due to an excessive request rate.' in page:
            logger.warning(page)
            break

        soup = BeautifulSoup(page, 'html.parser')
        a_tags = soup.find_all('a', href=True)
        for a_tag in a_tags:
            artwork_url = a_tag['href']
            #artwork links has div=glink
            div = a_tag.find('div', class_='glink')
            if div:
                artwork_title = div.get_text(strip=True)
                artwork_title = re.sub(invalid_chars, '_', artwork_title)
                artwork_title_to_url[artwork_title] = artwork_url
                last_artwork_url = artwork_url

        for artwork_title, artwork_url in artwork_title_to_url.items():
            download_one_artwork(artwork_url, artwork_title, ext)

        #used for turning page
        if last_artwork_url:
            last_artwork_id = last_artwork_url.split('/')[4]
            query_dict['next'] = last_artwork_id
            query = urllib.parse.urlencode(query_dict)

    return