import sqlite3
import datetime
import pandas as pd
import random
import matplotlib
matplotlib.use("Agg")                   # メインスレッド外で使うときはこうする
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import cv2
import base64

class DB():
    def __init__(self):
        """
        初期設定
        """
        self.dbname = "agri.db"                                         # データベース名
        self.get_config()                                               # 設定データを読み込む
        self.dpi = 72                                                   # グラフ作成時のdpi
        plt.rcParams["figure.dpi"] = self.dpi
        plt.rcParams["font.family"] = "MS Gothic"
        plt.rcParams["font.size"] = 20
    
    def get_config(self):
        """
        設定データを取得する
        """
        conn = sqlite3.connect(self.dbname)
        sql = f"SELECT * FROM config"
        df = pd.read_sql_query(sql, conn)                               # sql実行しpandas形式で格納する
        conn.close()
        df = df.set_index("index")                                      # index列をインデックスに設定する
        dict = {}
        for index, row in df.iterrows():                                # dataframeを辞書にする
            dict[index] = row["value"]
        # 辞書の中でよく使う値を変数として設定する
        self.sunlight_from =  dict["sunlight_from"]                     # LED点灯時間累計の始点
        self.temperature_from =  dict["temperature_from"]               # 温度累計の始点
        self.ephem_config = {   "place": dict["place"],
                                "lat": dict["lat"],
                                "lon": dict["lon"],
                                "elev": dict["elev"],
                            }
        return dict


    def set_config(self, dict):
        """
        設定データを書き込む
        """
        df = pd.DataFrame(index=[], columns=["index", "value"])         # 空のデータフレームを用意する
        for key, value in dict.items():                                 # 辞書をデータフレームにする
            df.loc[key] = [key, value]
        conn = sqlite3.connect(self.dbname)
        cur = conn.cursor()
        df.to_sql("config", conn, if_exists="replace", index=None)      # dfをデータベースに書き込む
        cur.close()
        conn.close()
        self.sunlight_from = df.at["sunlight_from", "value"]                     # LED点灯時間累計の始点
        self.temperature_from = df.at["temperature_from", "value"]               # 温度累計の始点


    def set_temperature(self, temp, humi, dt=None):
        """
        温湿度をデータベースに登録する
        Args:
            temp: 温度
            humi: 湿度
            dt  : 日時（文字列） 未指定ならば今
        """
        conn = sqlite3.connect(self.dbname)
        cur = conn.cursor()

        if dt is None:                                                  # 日時がNoneだったら
            dt = datetime.datetime.now()                                # 現在時刻
            strdt = dt.strftime("%Y/%m/%d %H:%M")                       # 日時の文字列
            strdate = dt.strftime("%Y/%m/%d")                           # 日付の文字列
        else:                                                           # 日時が文字列として与えられていたら
            strdt = dt                                                  # それが日時の文字列
            strdate = dt.split(" ")[0]                                  # スペースで区切った最初のほうが日付

        sql = f"INSERT INTO temperature VALUES('{strdate}','{strdt}', {temp}, {humi})"
        cur.execute(sql)
        conn.commit()
        cur.close()
        conn.close()
        self.set_summary(strdate)                                       # その日のサマリーデータを更新する


    def set_summary(self, date):
        """
        サマリーデータを登録する
        Args:
            date: 日付（文字列）
        """
        conn = sqlite3.connect(self.dbname)
        cur = conn.cursor()
        summary_exists = self.exists("summary", date)                   # サマリーにその日のデータがあるか

        temp_exists = self.exists("temperature", date)                  # 温湿度テーブルにその日のデータがあるか
        if temp_exists:                                                 # あるならば
            df = self.get_temperature(date)                             # その日の温湿度データを取得する
            max_temp = df["temperature"].max()                          # その日の最高気温
            min_temp = df["temperature"].min()                          # その日の最低気温
            mean_temp = (max_temp+min_temp)/2                           # 最高気温と最低気温の中間
            if summary_exists:                                          # サマリーにその日のデータがあれば更新する
                sql = f"UPDATE summary"\
                        f" SET max_temp={max_temp}, min_temp={min_temp}, mean_temp={mean_temp}"\
                        f" WHERE date='{date}'"
            else:                                                       # データがなければ追加挿入する
                sql = f"INSERT INTO summary(date, max_temp, min_temp, mean_temp)"\
                        f" VALUES('{date}','{max_temp}', {min_temp}, {mean_temp})"
            cur.execute(sql)
            conn.commit()

        led_exists = self.exists("LED", date)                           # LEDテーブルにその日のデータがあるか
        if led_exists:                                                  # あるならば
            df = self.get_LED(date)                                     # その日のLEDデータを取得する
            lighting_minutes = df["minute"].sum()                       # その日のLED点灯時間の合計
            if summary_exists:                                          # サマリーにその日のデータがあれば更新する
                sql = f"UPDATE summary"\
                        f" SET lighting_minutes={lighting_minutes}"\
                        f" WHERE date='{date}'"
            else:                                                       # データがなければ追加挿入する
                sql = f"INSERT INTO summary(date, lighting_minutes)"\
                        f" VALUES('{date}', {lighting_minutes})"
            cur.execute(sql)
            conn.commit()

        cur.close()
        conn.close()


    def get_temperature(self, date=None):
        """
        データベースから指定した日の温湿度データを取り出す
        Args:
            date : 日付（文字列）Noneならば今日
        Returns:
            df   : dataframe
        """
        conn = sqlite3.connect(self.dbname)
        if date is None:                                                # 日付がNoneだったら
            date = datetime.date.today().strftime("%Y/%m/%d")           # 今日の文字列

        sql = f"SELECT * FROM temperature WHERE date='{date}' ORDER BY date ASC"
        df = pd.read_sql_query(sql, conn)                               # sql実行しpandas形式で格納する
        df["datetime"] = pd.to_datetime(df["datetime"])                 # 文字列の日時をdatetimeに変換する
        conn.close()
        return df


    def get_LED(self, date=None):
        """
        データベースから指定した日のLEDデータを取り出す
        Args:
            date : 日付（）Noneならば今日
        Returns:
            df   : dataframe
        """
        conn = sqlite3.connect(self.dbname)
        if date is None:                                                # 日付がNoneだったら
            date = datetime.date.today().strftime("%Y/%m/%d")           # 今日の文字列

        sql = f"SELECT * FROM LED WHERE date='{date}' ORDER BY date ASC"
        df = pd.read_sql_query(sql, conn)                               # sql実行しpandas形式で格納する
        conn.close()
        return df

    def get_summary(self, sunlight_from, temperature_from, date=None, days=7):
        """
        サマリーを取得する
        Args:
            sunlight_from: LED点灯時間の累計の始点
            temperature_from: 温度の累計の始点
            date_to: 日付（文字列）未指定ならば今日
            days   : 何日前までか
        Return:
            dict      : 辞書
            light_b64 : 点灯時間のグラフ
            temp_b64  : 温度のグラフ
        """
        if date is None:                                                # 日付がNoneだったら
            date = datetime.date.today()                                # 今日（datetime型）
        else:                                                           # 日付が文字列として与えられていたら
            date = datetime.datetime.strptime(date, "%Y/%m/%d")         # 日付の計算をするためにdatetime型にする

        date_from = date - datetime.timedelta(days = days-1)            # 何日前（datetime型）
        date_from = date_from.strftime("%Y/%m/%d")                      # datetime型を文字列にする
        date_to = date.strftime("%Y/%m/%d")                             # datetime型を文字列にする
        conn = sqlite3.connect(self.dbname)

        # 点灯時間の集計
        sql = f"SELECT date, lighting_minutes FROM summary"\
                f" WHERE date BETWEEN '{sunlight_from}' AND '{date_to}'"\
                f" ORDER BY date ASC"
        df_sunlight = pd.read_sql_query(sql, conn)                      # LED点灯時間のみのデータフレーム
        df_sunlight = df_sunlight.set_index("date")                     # date列をインデックスに設定する
        df_sunlight = df_sunlight.sort_index()                          # インデックスでソートする
        df_sunlight = df_sunlight.cumsum()                              # 各日のデータを累積和にする
        df_sunlight = df_sunlight.rename(columns={"lighting_minutes": "lighting_minutes_sum"})      # 列名変更

        # 温度の集計
        sql = f"SELECT date, mean_temp FROM summary WHERE date BETWEEN '{temperature_from}' AND '{date_to}'"
        df_temp = pd.read_sql_query(sql, conn)                          # 平均気温のみのデータフレーム
        df_temp = df_temp.set_index("date")                             # date列をインデックスに設定する
        df_temp = df_temp.sort_index()                                  # インデックスでソートする
        df_temp = df_temp.cumsum()                                      # 各日のデータを累積和にする
        df_temp = df_temp.rename(columns={"mean_temp": "mean_temp_sum"})        # 列名変更

        sql = f"SELECT * FROM summary"\
                f" WHERE date BETWEEN '{date_from}' AND '{date_to}'"\
                f" ORDER BY date ASC"
        df = pd.read_sql_query(sql, conn)                               # サマリーのデータフレーム
        df = df.set_index("date")                                       # date列をインデックスに設定する
        conn.close()

        df = df.join(df_sunlight, how="left")                           # サマリーにLED点灯時間累計データをジョインする
        df = df.join(df_temp, how="left")                               # サマリーに温度累計データをジョインする
        dates = df.index.tolist()                                       # インデックス（日付）のリスト
        dict = {}
        for d in dates:                                                 # 各日付において
            dict[d] = { "max_temp": df.at[d, "max_temp"],
                        "min_temp": df.at[d, "min_temp"],
                        "mean_temp": df.at[d, "mean_temp"],
                        "lighting_minutes": df.at[d, "lighting_minutes"],
                        "lighting_minutes_sum": df.at[d, "lighting_minutes_sum"],
                        "mean_temp_sum": df.at[d, "mean_temp_sum"],
                        }                                               # 日ごとの辞書として登録する

        # サマリーグラフ
        light_b64, temp_b64 = self.draw_graph(dict)
        return dict, light_b64, temp_b64

    def exists(self, table, date):
        """
        指定した日のデータがテーブルににあるかどうか
        Args:
            table : テーブル名 date列があることが前提
            date  : 日付（文字列）
        Returns:
            bool  : True / False
        """
        conn = sqlite3.connect(self.dbname)
        cur = conn.cursor()
        sql = f"SELECT COUNT(date) FROM {table} WHERE date='{date}'"
        cur.execute(sql)
        cnt = cur.fetchone()[0]                                         # fetchは要素1のタプルを返すので、その要素を取り出す
        cur.close()
        conn.close()
        bool = True if cnt else False                                   # 1以上ならばTrue、0ならFalse
        return bool

    def set_LED(self, minute):
        """
        LED点灯時間をDBに追加する
        Args:
            minute : 時間（分）
            _      : 登録日時指定不可（今を点灯終了時刻とする）
        """
        conn = sqlite3.connect(self.dbname)
        cur = conn.cursor()
        now = datetime.datetime.now()                                   # 今
        date = now.strftime("%Y/%m/%d")                                 # 日付
        dt_to = now.strftime("%Y/%m/%d %H:%M")                          # 点灯終了時刻（今）
        df_from = (now - datetime.timedelta(minutes=minute)).strftime("%Y/%m/%d %H:%M")     # 点灯開始時刻
        sql = f"INSERT INTO LED VALUES('{date}','{df_from}', '{dt_to}', {minute})"
        cur.execute(sql)
        conn.commit()
        cur.close()
        conn.close()
        self.set_summary(date)                                          # その日のサマリーデータを更新する


    def getLED(self, date=None):
        """
        LEDデータを取得する
        Args:
            date: 日付（文字列）Noneならば今日
        """
        if date is None:                                                # 日付がNoneだったら
            date = datetime.date.today().strftime("%Y/%m/%d")           # 今日の文字列
        conn = sqlite3.connect(self.dbname)
        cur = conn.cursor()
        sql = f"SELECT * FROM LED WHERE date='{date}' ORDER BY date ASC"
        df = pd.read_sql_query(sql, conn)                               # sql実行しpandas形式で格納する
        cur.close()
        conn.close()
        return df


    def toCSV(self, table, date=None, days=0):
        """
        DBをcsvとして保存する
        Args:
            table : テーブル名
            date  : 日付（テキスト）
            days  : dateから何日前まで
        """
        conn = sqlite3.connect(self.dbname)
        if date is None:                                                # 日付がNoneだったら
            date = datetime.date.today()                                # 今日まで
        else:                                                           # 日付が文字列として与えられていたら
            date = datetime.datetime.strptime(date, "%Y/%m/%d")         # それをdatetimeにする

        date_to = date.strftime("%Y/%m/%d")                             # datetimeを文字列にする
        date_from = date - datetime.timedelta(days = days)              # 何日前
        date_from = date_from.strftime("%Y/%m/%d")                      # datetimeを文字列にする
        sql = f"SELECT * FROM {table} WHERE date BETWEEN '{date_from}' AND '{date_to}'"
        df = pd.read_sql_query(sql, conn)                               # sql実行しpandas形式で格納する
        df.to_csv(f"{table}.csv", index=False ,header=True)             # インデックス無しでcsv保存する
        conn.close()


    def set_ephem(self, dict):
        """
        日の出・日の入り時刻をサマリーに登録する
        Args:
            dict : 辞書
        """
        date = datetime.datetime.today().strftime("%Y/%m/%d")           # 今日の日付（文字列）
        sunrise_time = dict["sunrise_time"]
        sunset_time = dict["sunset_time"]
        moon_phase = dict["moon_phase"]

        summary_exists = self.exists("summary", date)                   # サマリーにその日のデータがあるかどうか
        if summary_exists:                                              # データがあれば更新する
            sql = f"UPDATE summary "\
                    f" SET sunrise_time='{sunrise_time}', sunset_time='{sunset_time}', moon_phase={moon_phase}"\
                    f" WHERE date='{date}'"
        else:                                                           # データがなければ追加挿入する
            sql = f"INSERT INTO summary(date, sunrise_time, sunset_time, moon_phase, lighting_minutes) "\
                    f" VALUES('{date}','{sunrise_time}', '{sunset_time}', {moon_phase}, 0)"

        conn = sqlite3.connect(self.dbname)
        cur = conn.cursor()
        cur.execute(sql)
        conn.commit()
        cur.close()
        conn.close()


    def delete(self, date_from):
        """
        指定した日以前のデータベースを削除する
        Args:
            date_from : 日付（文字列）
        """
        conn = sqlite3.connect(self.dbname)
        cur = conn.cursor()
        sql = "SELECT name FROM sqlite_master WHERE type='table'"       # DB内の全テーブル取得するSQL
        cur.execute(sql)
        tables = cur.fetchall()                                         # DB内の全テーブル　要素1のタプルのリスト
        tables = [table[0] for table in tables]                         # タプルのリストを単純なリストにする

        for table in tables:                                            # 各テーブルにおいて
            if table != "config":                                       # configでなかったら
                sql = f"DELETE FROM {table} WHERE date<='{date_from}'"  # データ削除するSQL
                cur.execute(sql)
        conn.commit()
        cur.close()
        conn.close()

    def draw_graph(self, dict):
        width_px, height_px = 900, 200                                  # ピクセルでのサイズ
        width_in = width_px/self.dpi                                    # インチでのサイズ（整数でなくてもよい）
        height_in = height_px/self.dpi
        x = [key for key in dict.keys()]

        # 温度のグラフ
        fig, ax = plt.subplots(figsize=(width_in, height_in))
        y_max = [item["max_temp"] for item in dict.values()]
        y_min = [item["min_temp"] for item in dict.values()]
        y_mean = [item["mean_temp"] for item in dict.values()]
        ax.plot(x, y_max, ":b", linewidth=1)
        ax.plot(x, y_min, ":b", linewidth=1)
        ax.plot(x, y_mean, ".-b", linewidth=2)
        ax.set_title("最高・最低・平均気温")
        ax.set_ylabel("気温（度）")
        fig.tight_layout()
        for i, value in enumerate(y_mean):
            ax.text(x[i], y_mean[i]+ 2, value)
            fig.canvas.draw()
        temp_b64 = fig2str64(fig)

        # 点灯時間のグラフ
        fig, ax = plt.subplots(figsize=(width_in, height_in))
        y = [item["lighting_minutes"] for item in dict.values()]
        ax.plot(x, y, ".-", linewidth=2, color="orange")
        ax.set_title("日当たりのLED点灯時間")
        ax.set_ylabel("時間（分）")
        fig.tight_layout()
        for i, value in enumerate(y):
            ax.text(x[i], y[i]+ 2, value)
            fig.canvas.draw()
        light_b64 = fig2str64(fig)
        return light_b64, temp_b64


    def draw_dailygraph(self, date=None, isLED=None, dt_from=None):
        """
        デイリーグラフ
        Args:
            date: 日付（文字列）Noneならば今日
        """
        dt_now = datetime.datetime.now()
        if date is None:                                                # 日付がNoneだったら
            date = datetime.date.today().strftime("%Y/%m/%d")           # 今日の文字列

        # 指定した日のサマリーデータ取得する
        conn = sqlite3.connect(self.dbname)
        cur = conn.cursor()
        sql = f"SELECT sunrise_time, sunset_time, lighting_minutes, mean_temp FROM summary WHERE date='{date}'"
        cur.execute(sql)
        result = cur.fetchall()[0]                                      # fetchはリストを返すのでその中身を取得する
        cur.close()
        conn.close()
        sunrise_time, sunset_time, lighting_minutes, mean_temp = result
        dt_sunrise = datetime.datetime.strptime(f"{date} {sunrise_time}", "%Y/%m/%d %H:%M")
        dt_sunset = datetime.datetime.strptime(f"{date} {sunset_time}", "%Y/%m/%d %H:%M")
        dt_0 = datetime.datetime.strptime(f"{date} 00:00", "%Y/%m/%d %H:%M")
        dt_24 = datetime.datetime.strptime(f"{date} 23:59", "%Y/%m/%d %H:%M")

        width_px, height_px = 900, 200                                  # ピクセルでのサイズ
        width_in = width_px/self.dpi                                    # インチでのサイズ（整数でなくてもよい）
        height_in = height_px/self.dpi

        # LEDの一日グラフ
        df = self.get_LED(date)                                         # 点灯データ取得する
        df = df.sort_values("datetime_from")                            # datetime_from列でソート
        df["datetime_from"] = pd.to_datetime(df["datetime_from"])       # 日時を文字列からdatetimeにする
        df["datetime_to"] = pd.to_datetime(df["datetime_to"])           # 日時を文字列からdatetimeにする
        x = [dt_0]                                                      # xの初期値 0時0分
        y = [0]                                                         # yの初期値 0（点灯オフ）
        for dt_from, dt_to in zip(df["datetime_from"], df["datetime_to"]):      # 各行について
            x.extend([dt_from, dt_from, dt_to, dt_to])                          # 「冂」状のグラフを作るためのx
            y.extend([0, 1, 1, 0])                                              # 「冂」状のグラフを作るためのy
        if isLED:                                                       # 現在点灯中ならば
            x.extend([dt_from, dt_from, dt_now, dt_now])                # 追加で「冂」状のグラフを作るためのx
            y.extend([0, 1, 1, 0])                                      # 追加で「冂」状のグラフを作るためのy
        x.append(dt_24)                                                 # 23:59
        y.append(0)                                                     # 23:59は0




        fig, ax = plt.subplots(figsize=(width_in, height_in))
        ax.set_xlim(dt_0, dt_24)                                        # x軸の範囲
        ax.set_ylim(0, 1)                                               # y軸の範囲
        locator = mdates.AutoDateLocator()
        locator.intervald["HOURLY"] = 3                                 # x軸 3時間ごとに目盛表記
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H"))        # x軸の書式
        plt.yticks(color="None")                                        # y軸は目盛なし
        ax.fill_between(x, y, "-", linewidth=2, color="orange")         # プロット y軸との間塗りつぶし
        ax.set_title(f"{date}の点灯時間 合計{lighting_minutes}分")      # タイトル
        ax.axvspan(dt_0, dt_sunrise, color="gray", alpha=0.3)           # 夜の背景
        ax.axvspan(dt_sunset, dt_24, color="gray", alpha=0.3)           # 夜の背景
        fig.tight_layout()
        fig.canvas.draw()
        light_b64 = fig2str64(fig)

        # 温度の一日グラフ
        df = self.get_temperature(date)
        df = df.set_index("datetime")                                   # datetime列をインデックスにする
        df = df.sort_index()                                            # 時間（インデックス）で並び替え
        fig, ax = plt.subplots(figsize=(width_in, height_in))
        x = df.index.to_list()
        x.append(dt_now)                                                # 現在時刻を追加
        y = df["temperature"].tolist()
        y.append(y[-1])                                                 # 直近の温度を追加
        ax.set_xlim(dt_0, dt_24)                                        # x軸の範囲
        locator = mdates.AutoDateLocator()
        locator.intervald["HOURLY"] = 3                                 # x軸 3時間ごとに目盛表記
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H"))        # x軸の書式
        ax.plot(x, y, "-b", linewidth=2)                                # 折れ線グラフ
        ax.set_title(f"{date}の気温 平均{mean_temp}度")                 # タイトル
        ax.axvspan(dt_0, dt_sunrise, color="gray", alpha=0.3)           # 夜の背景
        ax.axvspan(dt_sunset, dt_24, color="gray", alpha=0.3)           # 夜の背景
        fig.tight_layout()
        fig.canvas.draw()
        temp_b64 = fig2str64(fig)
        return light_b64, temp_b64


def fig2str64(fig):
    img = np.array(fig.canvas.renderer.buffer_rgba())           # numpy配列にする
    img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)                 # OpenCV画像にする
    _, imgEnc = cv2.imencode(".jpg", img)                       # メモリ上にエンコード
    imgB64 = base64.b64encode(imgEnc)                           # base64にエンコード
    strB64 = "data:image/jpg;base64," + str(imgB64, "utf-8")    # 文字列化
    return strB64


db = DB()

def main():
    dict = db.draw_dailygraph()



if __name__ == "__main__":
    main()

