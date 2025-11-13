import time
import requests
import pyautogui as pa
import tkinter as tk
import tkinter.messagebox as mb
import pandas as pd

from tkinter import ttk
from tkinter import messagebox

pa.FAILSAFE = True

def execute():
    # 実行ボタンの動作

    date_eating = text_eating.get()  # 献立日

    tk.Tk().withdraw()

    res = requests.get('https://order.dan1.jp/media/output/rakukon/autoinput/' + date_eating + '.txt')

    filename = 'auto_input.csv'

    urlData = res.content

    with open(filename, mode='wb') as f:  # wb でバイト型を書き込める
        f.write(urlData)

    if res.status_code == 404:
        mb.showinfo('エラー', '集計データが見つかりません。\n\n\
        入力する喫食日の食数集計表を先に作成してください。')
    else:
        mb.showinfo('準備完了', '10秒後に自動入力が始まります。OKボタンを押したあと、\n\nらくらく献立の「フリーズ」の先頭をクリックしてご準備ください。\n\n（マウスを画面の角に移動させると自動処理が停止します）')

        time.sleep(10)

        df_shokusu = pd.read_csv(filename, header=None)

        lists = df_shokusu[0]

        list_texts = [str(n) for n in lists]

        for i in list_texts:
            pa.write(i)
            pa.press('enter')

        messagebox.showinfo("完了", "完了しました。")


# メインウィンドウ
main_win = tk.Tk()
main_win.title("らくらく献立に食数を入力します")
main_win.geometry("500x100+500+300")


# メインフレーム
main_frm = ttk.Frame(main_win)
main_frm.grid(column=0, row=0, sticky=tk.NSEW)


# パラメータ
file_joh = tk.StringVar()
text_eating = tk.StringVar()


# ウィジェット作成
eating_label = ttk.Label(main_frm, text="喫食日（YYYY-MM-DD）")
eating_box = ttk.Entry(main_frm, textvariable=text_eating)

app_btn = ttk.Button(main_frm, text="処理開始", command=execute)


# ウィジェットの配置
eating_label.pack(padx=5, pady=5, side=tk.LEFT, fill=tk.Y)
eating_box.pack(padx=5, pady=5, side=tk.LEFT)

app_btn.pack(padx=5, pady=5, side=tk.LEFT)


# 配置設定
main_win.columnconfigure(0, weight=1)
main_win.rowconfigure(0, weight=1)
main_frm.columnconfigure(1, weight=1)

main_win.protocol("WM_DELETE_WINDOW", main_win.quit)
main_win.mainloop()
