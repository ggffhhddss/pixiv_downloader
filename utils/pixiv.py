from secrets import token_urlsafe
from hashlib import sha256
import time
import os
from urllib.parse import urlencode
from base64 import urlsafe_b64encode
import requests
from playwright.sync_api import sync_playwright
from pixivpy3 import AppPixivAPI
from .shared import *

# Latest app version can be found using GET /v1/application-info/android
USER_AGENT = "PixivAndroidApp/5.0.234 (Android 11; Pixel 5)"
REDIRECT_URI = "https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback"
LOGIN_URL = "https://app-api.pixiv.net/web/v1/login"
AUTH_TOKEN_URL = "https://oauth.secure.pixiv.net/auth/token"
CLIENT_ID = "MOBrBDS8blbauoSck0ZfDbtuzpyT"
CLIENT_SECRET = "lsACyCD94FhDUtGTXi3QzcFE2uU1hqtDaKeqrdwj"
FILTER_TYPE = ["user_id", "tag"]
WORK_TYPE = ["illust", "manga"]

from dotenv import load_dotenv
load_dotenv()
   
pixiv_username = os.getenv('pixiv_username')
pixiv_password = os.getenv('pixiv_password')

def s256(data):
    """S256 transformation method."""
    return urlsafe_b64encode(sha256(data).digest()).rstrip(b"=").decode("ascii")

def oauth_pkce(transform):
    """Proof Key for Code Exchange by OAuth Public Clients (RFC7636)."""

    code_verifier = token_urlsafe(32)
    code_challenge = transform(code_verifier.encode("ascii"))

    return code_verifier, code_challenge


url_prefix = 'https://app-api.pixiv.net/web/v1/login'
code_verifier, code_challenge = oauth_pkce(s256)
url_params = {
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "client": "pixiv-android",
    }
URL = f"{url_prefix}?{urlencode(url_params)}"

def get_refresh_code_from_pixiv(url=URL):

    codes = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            permissions=[],
            viewport={"width": 1280, "height": 800},
            service_workers="block"
            )
        page = context.new_page()

        page.goto(url)
        time.sleep(5)
        page.get_by_placeholder("E-mail address or pixiv ID").fill(pixiv_username)
        page.get_by_placeholder("Password").fill(pixiv_password)
        time.sleep(1)
        page.click("button.charcoal-button[type='submit'][data-variant='Primary']")
        time.sleep(15)

        #sometimes there's a security check page popping up
        if page.locator("button", has_text="Remind me later").count()>0:
            page.click("button.charcoal-button:has-text('Remind me later')")

        def find_code(request):
            if "code=" in request.url and "https://app-api.pixiv.net" in request.url:
                code = request.url.split('code=')[1]
                codes.append(code)   
        page.on("request", find_code)

        #if after 20s still cant find codes, error
        countdown = 20
        while not codes and countdown>0:
            time.sleep(1)
            countdown -= 1

        browser.close()
    
    code = codes[0]
    print('successfully get refresh code')

    #ref: https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362
    response = requests.post(
            AUTH_TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
                "code_verifier": code_verifier,
                "grant_type": "authorization_code",
                "include_policy": "true",
                "redirect_uri": REDIRECT_URI,
            },
            headers={"User-Agent": USER_AGENT},
        )
    data = response.json()
    access_token = data["access_token"]
    refresh_token = data["refresh_token"]

    #save tokens to local
    update_or_add_env_variable(key='access_token', value=access_token)
    update_or_add_env_variable(key='refresh_token', value=refresh_token)

    return access_token, refresh_token

def get_refresh_code_from_local():

    access_token = os.getenv('access_token')
    refresh_token = os.getenv('refresh_token')

    #test if local refresh token works
    api = AppPixivAPI()
    api.set_auth(access_token, refresh_token)
    try:
        json_result = api.illust_detail(59580629)
        if 'error' in json_result:
            access_token, refresh_token = get_refresh_code_from_pixiv()
    except Exception:
        access_token, refresh_token = get_refresh_code_from_pixiv()

    return access_token, refresh_token


access_token, refresh_token = get_refresh_code_from_local()
api = AppPixivAPI()
api.set_auth(access_token, refresh_token)

def get_works(api, filter_type:str, tag:str, user_id:str, work_type:str, offset:int, disable_ai:bool=True):
    
    if work_type == 'illust':

        if filter_type == 'tag':
            illustrations = api.search_illust(word=tag, search_ai_type=disable_ai, type=work_type, offset=offset)
        elif filter_type == 'user_id':
            illustrations = api.user_illusts(user_id=user_id, type=work_type, offset=offset)
        if 'illusts' in illustrations.keys():
            return illustrations['illusts']
        else:
            return []
        
    if work_type == 'manga':

        if filter_type == 'tag':
            illustrations = api.search_illust(word=tag, search_ai_type=disable_ai,type=work_type, offset=offset)
        elif filter_type == 'user_id':
            illustrations = api.user_illusts(user_id=user_id,type=work_type, offset=offset)
        if 'illusts' in illustrations.keys():
            return illustrations['illusts']
        else:
            return []
    
    if work_type == 'novel':
        if filter_type == 'tag':
            novels = api.search_novel(word=tag, search_ai_type=disable_ai, offset=offset)
        elif filter_type == 'user_id':
            novels = api.user_novels(user_id=user_id, offset=offset)

        if 'novels' in novels.keys():
            return novels['novels']
        else:
            return []
        

def pixiv_download_illstrations(api: AppPixivAPI, filter_type: str, work_type:str ='illust', max_num:int = -1, tag: str=None, disable_ai:bool = 1, user_id: str=None, popularity_threshold:dict= {'total_view':0,'total_bookmarks':0}):
    """
    Parameters:
        filter_type:'tag' or 'user_id', must include tag in params if set to 'tag', must include user_id in params if set to 'user_id'
        work_type: 'illust' or 'manga'
        api (PixivAPI): Authenticated PixivAPI instance.
        user_id (int): Pixiv user ID.
        save_dir (str): Folder where images will be saved.
        max_num: maximum amount of imgs to be downloaded, set to -1 means no limit
        popuar_threshold: threshold for total views adn bookmarks, used as a naive way to infer img quality

    format of muti tags: 
        tag = 'woman cute' gives pics that tagged both woman and cute
        tag = 'woman -cute -solo' gives pics that tagged woman but exclude cute and solo

    """

    # Create download directory if it doesn't exist
    #os.makedirs(save_dir, exist_ok=True)

    assert filter_type in ['tag','user_id']
    assert type(max_num) == int and max_num >= -1

    #if use user_id, get user name
    if filter_type == 'user_id':
        user_detail = api.user_detail(user_id)
        user_name = clean_text(user_detail.user.name)
        base_save_dir = f"download/pixiv/illust/{work_type}/{filter_type}/{user_name}_{user_id}"
    
    elif filter_type == 'tag':
        base_save_dir = f"download/pixiv/{work_type}/{filter_type}/{tag}"

    # Pagination support
    offset = 0
    count = 0

    try:
        works = get_works(api, filter_type, tag, user_id, work_type, offset, disable_ai)
    except Exception:
        access_token, refresh_token = get_refresh_code_from_pixiv()
        api.set_auth(access_token, refresh_token)
        works = get_works(api, filter_type, tag, user_id, work_type, offset, disable_ai)

    while works:
        
        for illust in works:

            # filter by popularity
            if all([illust[key]>popularity_threshold[key] for key in popularity_threshold.keys()]):
                title = clean_text(illust['title'])
                save_dir =f'{base_save_dir}/{title}_{illust.id}'
                try:
                    os.makedirs(save_dir, exist_ok=True)
                #if title contain unsupported character, dont include it in filename
                except OSError:
                    save_dir =f'{base_save_dir}/{clean_text(title)}_{illust.id}'
                    os.makedirs(save_dir, exist_ok=True)

                print(f"Downloading: {title} -> {save_dir}")
                time.sleep(1)

                # if illust has muti pages
                if illust['meta_pages']:
                    pages = illust['meta_pages']
                    image_urls = [page['image_urls']['large'] for page in pages]
                # if only one page
                elif illust['meta_single_page']:
                    pages = illust['meta_single_page']
                    image_urls = [ pages['original_image_url'] ]

                #check if is already downloaded
                if len([f for f in os.listdir(save_dir)]) < len(image_urls):
                    page_idx = 0
                    for image_url in image_urls:

                        ext = os.path.splitext(image_url)[1]
                        
                        if not os.path.exists(f"{save_dir}/{page_idx}{ext}"):
                            time.sleep(1)
                            #if access_token outdated, fetch again
                            try:
                                api.download(url=image_url,path=save_dir,name=f"{page_idx}{ext}")
                            except Exception:
                                access_token, refresh_token = get_refresh_code_from_pixiv()
                                api.set_auth(access_token, refresh_token)
                                api.download(url=image_url,path=save_dir,name=f"{page_idx}{ext}")
                        page_idx+=1

                    count += 1

                else:
                    print('already downloaded.')

                offset += 1
                
                if max_num != -1:
                    if count >= max_num: 
                        return 

        try:
            works = get_works(api, filter_type, tag, user_id, work_type, offset, disable_ai)
        except Exception:
            access_token, refresh_token = get_refresh_code_from_pixiv()
            api.set_auth(access_token, refresh_token)
            works = get_works(api, filter_type, tag, user_id, work_type, offset, disable_ai)



def pixiv_download_novels(filter_type: str, strmax_num:int = -1, tag: str=None, disable_ai:bool = 1, user_id: str=None, max_num: int=-1, popularity_threshold:dict= {'total_view':0,'total_bookmarks':0}, if_translate: bool=0, dest:str ='zh-CN'):

    assert filter_type in ['tag','user_id']
    assert type(max_num) == int and max_num >= -1

    if filter_type == 'user_id':
        user_detail = api.user_detail(user_id)
        user_name = clean_text(user_detail.user.name)
        base_save_dir = f"download/pixiv/novel/{filter_type}/{user_name}_{user_id}"
    
    if filter_type == 'tag':
        base_save_dir = f"download/pixiv/novel/{filter_type}/{tag}"

    offset = 0
    count = 0
    novels = get_works(api, filter_type, tag, user_id, 'novel', offset, disable_ai)

    while novels:
        for novel in novels:
            if all([novel[key]>popularity_threshold[key] for key in popularity_threshold.keys()]):
                novel_id = novel['id']
                title = clean_text(novel['title'])
                file_name =(f'{title}_{novel_id}.txt')
                try:
                    save_dir = f'{base_save_dir}/{file_name}'
                    os.makedirs(base_save_dir, exist_ok=True)
                #if title contain unsupported character, dont include it in filename
                except OSError:
                    save_dir =f'{base_save_dir}/{clean_text(title)}_{novel_id}.txt'
                    os.makedirs(save_dir, exist_ok=True)

                print(f"Downloading: {title} -> {save_dir}")
                if not os.path.exists(save_dir):
                    novel_text = api.novel_text(novel_id=novel_id)['novel_text']
                    with open(save_dir, "w", encoding="utf-8") as f:
                        f.write(novel_text)
                else:
                    print('already downloaded.')
                #job.DownloadJob(f"https://www.pixiv.net/novel/show.php?id={novel_id}").run()
            
                count += 1

                if if_translate:
                    translated_save_dir =f'{base_save_dir}/{title}_{novel_id}_{dest}.txt' 
                    print(f"Translating: {title} -> {translated_save_dir}")
                    if not os.path.exists(translated_save_dir):
                        with open(save_dir, "r", encoding="utf-8") as f:
                            raw = f.read()
                        asyncio.run(translate_text(text=raw, save_dir=translated_save_dir))
                    else:
                        print('already translated.')
            offset += 1
    
        novels = get_works(api, filter_type, tag, user_id, 'novel', offset, disable_ai)


def pixiv_update_illstrations(api: AppPixivAPI, filter_type='user_id', work_type='illust'):
    '''
    get the latesest work from all tags/users in existing folders
    '''
    root = f'download/pixiv/illust/{work_type}/{filter_type}'
    for subfolder_name in os.listdir(root):
        user_id = subfolder_name.split('_')[-1]
        pixiv_download_illstrations(api=api, filter_type=filter_type, user_id=user_id, work_type=work_type)
        

user_ids = [34696662]

#update_illstrations(api=api)

