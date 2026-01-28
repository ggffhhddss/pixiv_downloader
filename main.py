from utils.pixiv import *
from utils.e_tentai import *

user_ids = [118890010]

#e.g. dl all kinds artworks from a user
'''
for user_id in user_ids:
    pixiv_download_illstrations(api=api,filter_type='user_id', user_id=user_id,tag='bondage', work_type='illust')
    pixiv_download_illstrations(api=api,filter_type='user_id', user_id=user_id,tag='bondage', work_type='manga')
    #download novel and translate
    pixiv_download_novels(filter_type='user_id', user_id=user_id,tag='bondage', if_translate=1, dest='en')
'''



#e.g. udate all existing pixiv folders
pixiv_update_illstrations(api=api)



#e.g. e-hentai download 
#eh_download(search_text='english', avoid_categories={'misc'})

