import time
import subprocess
import platform
import pandas as pd
import pyautogui as pa
import openpyxl as excel
import tkinter as tk
import tkinter.messagebox as mb
import requests

pa.FAILSAFE = True

# Windowsでメモ帳を起動
if platform.system() == 'Windows':
    subprocess.Popen(r'c:\Windows\notepad.exe')

# macOSでテキストエディットを起動
if platform.system() == 'Darwin':
    subprocess.Popen(['open', '/System/Applications/TextEdit.app'])

# res = requests.get('https://order.dan1.jp/media/output/rakukon/autoinput_2022-04-01.txt')
# pa.write(str(res.text))
# pa.press('enter')

tk.Tk().withdraw()
mb.showinfo('準備完了', '10秒後に自動入力が始まります。\n\n\
OKボタンを押したあと、食数入力画面の先頭をクリックしてご準備ください。\n\n\
（マウスを画面の角に移動させると自動処理が停止します）')


time.sleep(10)

df_shokusu = pd.read_excel('らくらく献立食数登録.xlsx', sheet_name='入力用', index_col=0)
df_shokusu = df_shokusu.fillna(0)
df_shokusu = df_shokusu.astype({'調整数': 'int64'})

lists = df_shokusu['調整数']
lists.to_csv("temp.csv", index=False, header=False)

book = excel.load_workbook('らくらく献立食数登録.xlsx')
sheet = book['入力用']
eating_day = sheet['H5'].value

worksheet = book.copy_worksheet(book['入力用'])
worksheet.title = eating_day

sheet = book['入力用']

for row in sheet['F2':'F505']:
    for cell in row:
        cell.value = None

book.save('らくらく献立食数登録.xlsx')


with open('temp.csv') as f:
    s = f.read()
    pa.write(s)
