import asyncio
import sqlite3
from googletrans import Translator
from functools import wraps
from re import split, sub


BASE_SAVE_DIR = './download'

#general
from dotenv import load_dotenv, set_key
import os

def update_or_add_env_variable(key, value, env_file='.env'):
    """
    Update an existing key's value in the .env file or add a new key-value pair if it doesn't exist.
    
    Args:
        env_file (str): The path to the .env file.
        key (str): The key (environment variable) to update or add.
        value (str): The value to assign to the key.
    """
    with open(env_file, "r") as env:
        lines = env.readlines()

    updated = False
    # Check if the key already exists and update its value
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            updated = True
            break

    # If the key wasn't found, append it to the end
    if not updated:
        lines.append(f"{key}={value}\n")

    # Write the updated content back to the .env file
    with open(env_file, "w") as env:
        env.writelines(lines)


def clean_text(text):
    return sub(r'[^a-zA-Z0-9\u4e00-\u9fff\uac00-\ud7af\u3130-\u318f一-龯々〆〤ーぁ-んァ-ヶａ-ｚＡ-Ｚ]', '_', text)

async def translate_text(save_dir:str, text: str, src: str=None, dest: str='zh-CN'):

    max_len = 1000

    async with Translator() as translator:

        if not src:
            src = await translator.detect(text[:100])
            src = src.lang

        if src != dest:

            paragraphs = split(r'(?<=\n)', text)
            bulk = ''
            translated = ''
            for paragraph in paragraphs:

                #if not too long after add the paragraph
                if len(bulk+paragraph)<=max_len:
                    bulk += paragraph
                # if too long after add the paragraph
                else:
                    bulk_translated = await translator.translate(bulk, src=src, dest=dest)
                    bulk_translated = bulk_translated.text
                    translated += bulk_translated
                    
                    #if paragraph not too long
                    if len(paragraph)<=max_len:
                        bulk = paragraph

                    #if paragrah itself too long
                    else:
                        bulk = ''
                        if src in ['zh','ja']:
                            sentences = split(r'(?<=[。?!])',paragraph)
                        else:
                            sentences = split(r'(?<=[.?!])',paragraph)
                        for sentence in sentences:
                            bulk += sentence
                            if len(bulk+sentence)>max_len:
                                
                                bulk_translated = await translator.translate(bulk, src=src, dest=dest)
                                bulk_translated = bulk_translated.text
                                translated += bulk_translated
                                bulk = sentence
            #last bulk
            bulk_translated = await translator.translate(bulk, src=src, dest=dest)
            bulk_translated = bulk_translated.text
            translated += bulk_translated
                
            with open(save_dir, "w", encoding='utf-8') as f:
                f.write(translated)

    return


#sql
def clear_sql_cache(table_name,sql_dir='%USERPROFILE%\\gallery-dl\\archive-pixiv.sqlite3'):
    try:
        conn = sqlite3.connect(sql_dir)
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table_name}")
        conn.commit()
        conn.close()
        print(f"All data in table {table_name} has been deleted.")
    except Exception:
        print('cannot claer cache')