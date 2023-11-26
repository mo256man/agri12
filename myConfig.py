import configparser
import os
import datetime
import re

# 設定ファイルのクラス
class Config():
    def __init__(self):
        self.filename = "config.ini"
        self.parser = configparser.ConfigParser()
        self.parser.optionxform = str               # 大文字小文字を区別する
        self.default_values = \
"""
[DEFAULT]
place = 名古屋
lat = 35.1667
lon = 136.9167
elev = 0
orning_offset = 0
evening_offset = 0
morning_minutes = 90
evening_minutes = 90
sensing_interval = 1
sensing_count = 2
output1 = 1
output2 = 1
output3 = 1
output4 = 1
batt_yellow = 5
batt_green = 20
"""

    def read(self):
        # 設定ファイルが存在しない場合、デフォルト設定を新規作成する
        if not os.path.exists(self.filename):
            with open(self.filename, mode="w", encoding="utf-8") as f:
                f.write(self.default_values)
        
        # 設定ファイルを読み込む 
        self.parser.read(self.filename, encoding="utf-8")
        return dict(self.parser["DEFAULT"])

    def write(self, dict):
        # 設定ファイルに書き込む
        self.parser["DEFAULT"].update(dict)
        with open(self.filename, mode="w",  encoding="utf-8") as f:
            self.parser.write(f)


# 日当たりログのクラス
class Dailylog():
    def __init__(self):
        self.filename = "日当たりログ.txt"                        # ファイル名

    def read_last_data(self):
        """
        最終行のデータを取得する
        """
        with open(self.filename, mode="r", encoding="utf-8") as f:
            str_list = f.readlines()                            # 全テキストを行単位のリストとして読み込む
        row_cnt = len(str_list)                                 # 行数
        last_row = str_list[row_cnt - 1]                        # 最終行の内容
        last_row_list = re.split("[,:]", last_row)              # 最終行の内容をコンマおよびコロンで区切ってリストとする

        last_date = last_row_list[0]                            # 最初の要素が日付
        last_value = last_row_list[2].strip()                   # 0から数えて2番めが今日の累計
        last_value = int(last_value[:-1])                       # 最後の1文字は「分」なので、それを除いて数値化する
        last_sum = last_row_list[-1].strip()                    # 最後の要素がこれまでの累計
        last_sum = int(last_sum[:-1])                           # 最後の1文字は「分」なので、それを除いて数値化する
        return last_date, last_value, last_sum
    
    def last_n_data(self, n=7):
        """
        最後の数行を取得する　n=行数
        """
        with open(self.filename, mode="r", encoding="utf-8") as f:
            str_list = f.readlines()                            # 全テキストを行単位のリストとして読み込む
        last_row = len(str_list)                                # 行数
        start_row = max(0, last_row-n)                          # 表示する最初の行
        text = "過去の実績<br><br>"
        for i in range(start_row, last_row):
            line = str_list[i]
            print(i, line)
            text += line + "<br>"
        return text

    def refresh_last(self, val):
        """
        最終行を更新する　val=追加する時間
        """
        print(f"今日のデータを{val}だけプラスするぞ")
        today = datetime.datetime.now().strftime("%Y/%m/%d")    # 今日の日付
        last_data = self.read_last_data()                       # ログの最終行のデータ
        last_date, last_value, last_sum = last_data             # 最終行の3つのデータ
        print(last_date, last_value, last_sum)

        if today != last_date:                                  # 日付が違っていたら
            with open(self.filename, mode="a",  encoding="utf-8") as f:
                last_date = today                               # 日付は今日
                last_value = 0                                  # 今日の累計は0
                f.write(f"{last_date},一日の実績:{last_value}分, 累計:{last_sum}分\n")        # 今日の行を追記する        

        last_value += val                                       # 今日1日のデータに今回の点灯時間をプラス
        last_sum += val                                         # これまでの累計データに今回の点灯時間をプラス

        with open(self.filename, mode="r", encoding="utf-8") as f:
            str_list = f.readlines()                            # 全テキストを行単位のリストとしてあらためて読み込む
        row_cnt = len(str_list)                                 # 行数
        print("更新前", str_list[row_cnt - 1])
        str_list[row_cnt - 1] = f"{today},一日の実績:{last_value}分, 累計:{last_sum}分\n"    # 更新する最終行
        print("更新後", str_list[row_cnt - 1])
        print(str_list)
        with open(self.filename, mode="w", encoding="utf-8") as f:
            f.writelines(str_list)                   # あらためて全行書き込む　最終行の更新はこうするしかない？
