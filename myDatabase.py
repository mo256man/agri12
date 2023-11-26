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
        sql = f"SELECT * FROM config"
        conn = sqlite3.connect(self.dbname)
        df = pd.read_sql_query(sql, conn)                               # sql実行しpandas形式で格納する
        conn.close()
        df = df.set_index("index")                                      # index列をインデックスに設定する
        dict = {}
        for index, row in df.iterrows():                                # dataframeを辞書にする
            dict[index] = row["value"]
        # 辞書の中でよく使う値を変数として設定する
        self.cumsum_date =  dict["cumsum_date"]                         # 累計の始点
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
        self.cumsum_date = df.at["cumsum_date", "value"]              # 累計の始点


    def set_temperature(self, temp, humi, strdt=None):
        """
        温湿度をデータベースに登録する
        Args:
            temp : 温度
            humi : 湿度
            strdt: 日時（文字列） Noneならば今
        Returns:
            imgB64: デイリーグラフ
        """
        if humi == -1:                                                  # 湿度が-1ならばセンサー値取得できていないので
            return "None"                                               # "None"を返す
        if strdt is None:                                               # 日時がNoneだったら
            dt = datetime.datetime.now()                                # 現在時刻
            strdt = dt.strftime("%Y/%m/%d %H:%M")                       # 日時の文字列
            strdate = dt.strftime("%Y/%m/%d")                           # 日付の文字列
        else:                                                           # 日時が文字列として与えられていたら
            strdate = dt.split(" ")[0]                                  # スペースで区切った最初のほうが日付

        sql = f"INSERT INTO temperature VALUES('{strdate}','{strdt}', {temp}, {humi})"
        conn = sqlite3.connect(self.dbname)
        cur = conn.cursor()
        cur.execute(sql)
        conn.commit()
        cur.close()
        conn.close()
        self.set_temp_summary(strdate)                                  # その日の温度サマリーデータを更新する
        imgB64 = self.make_daily_temp_graph(strdate)                    # デイリーデータ作成
        return imgB64


    def set_temp_summary(self, date):
        """
        温度のサマリーデータを登録する
        Args:
            date: 日付（文字列）
        """
        summary_exists = self.exists("summary", date)                   # サマリーにその日のデータがあるか
        temp_exists = self.exists("temperature", date)                  # 温湿度テーブルにその日のデータがあるか
        if temp_exists:                                                 # 温湿度テーブルにその日のデータがあるならば
            df = self.get_temperature(date)                             # その日の温湿度データを取得する
            max_temp = df["temperature"].max()                          # その日の最高気温
            min_temp = df["temperature"].min()                          # その日の最低気温
            mean_temp = (max_temp+min_temp)/2                           # 最高気温と最低気温の中間
            if summary_exists:                                          # サマリーにその日のデータがあれば更新する
                sql = f"UPDATE summary"\
                        f" SET max_temp={max_temp}, min_temp={min_temp}, mean_temp={mean_temp}"\
                        f" WHERE date='{date}'"
            else:                                                       # サマリーにその日のデータがなければ追加挿入する
                sql = f"INSERT INTO summary(date, max_temp, min_temp, mean_temp)"\
                        f" VALUES('{date}','{max_temp}', {min_temp}, {mean_temp})"
            conn = sqlite3.connect(self.dbname)
            cur = conn.cursor()
            cur.execute(sql)
            conn.commit()
            cur.close()
            conn.close()

    def make_daily_temp_graph(self, date=None):
        """
        温度デイリーグラフ
        Args:
            date: 日付（文字列）Noneならば今日
        Returns:
            strB64: 画像
        """
        if date is None:                                                # 日付がNoneだったら
            date = datetime.date.today().strftime("%Y/%m/%d")           # 今日の文字列

        conn = sqlite3.connect(self.dbname)
        cur = conn.cursor()
        # 温度データ取得
        sql = f"SELECT * FROM temperature WHERE date='{date}' ORDER BY date ASC"
        df = pd.read_sql_query(sql, conn)                               # sql実行しpandas形式で格納する
        # サマリーデータ取得
        sql = f"SELECT sunrise_time, sunset_time, mean_temp FROM summary WHERE date='{date}'"
        cur.execute(sql)
        result = cur.fetchall()[0]                                      # fetchはリストを返すのでその中身を取得する
        cur.close()
        conn.close()

        df["datetime"] = pd.to_datetime(df["datetime"])                 # 文字列の日時をdatetimeに変換する
        df = df.set_index("datetime")                                   # datetime列をインデックスにする
        df = df.sort_index()                                            # 時間（インデックス）で並び替え
        sunrise_time, sunset_time, mean_temp = result
        dt_now = datetime.datetime.now()                                # 今
        dt_sunrise = str2datetime(f"{date} {sunrise_time}")             # 日の出
        dt_sunset = str2datetime(f"{date} {sunset_time}")               # 日の入り
        dt_0 = str2datetime(f"{date} 00:00")                            # 指定した日の00:00のdatetime
        dt_24 = str2datetime(f"{date} 23:59")
        # グラフ描画
        x = df.index.to_list()
        y = df["temperature"].tolist()

        width_px, height_px = 900, 200                                  # ピクセルでのサイズ
        width_in, height_in = width_px/self.dpi, height_px/self.dpi     # インチでのサイズ（整数でなくてもよい）
        fig, ax = plt.subplots(figsize=(width_in, height_in))
        ax.spines["right"].set_visible(False)
        ax.spines["top"].set_visible(False)
        plt.gca().spines['right'].set_visible(False)
        plt.gca().spines['top'].set_visible(False)
        ax.set_xlim(dt_0, dt_24)
        locator = mdates.AutoDateLocator()
        locator.intervald["HOURLY"] = 3                                 # x軸 3時間ごとに目盛表記
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H"))
        ax.axvspan(dt_0, dt_sunrise, color="gray", alpha=0.3)           # 夜の背景
        ax.axvspan(dt_sunset, dt_24, color="gray", alpha=0.3)
        ax.vlines(dt_now, min(y), max(y), "RED")                        # 現在時刻に赤線
        ax.hlines(mean_temp, dt_0, dt_24, "BLUE", linestyles="dotted")
        ax.plot(x, y, "-b", linewidth=2)
        ax.set_title(f"{date}の気温 平均{mean_temp}度")
        fig.tight_layout()
        fig.canvas.draw()
        imgB64 = fig2str64(fig)
        return imgB64


    def get_LED(self, date=None):
        """
        DBから指定した日のLEDデータを取り出す
        Args:
            date : 日付（）Noneならば今日
        Returns:
            df   : dataframe
        """
        conn = sqlite3.connect(self.dbname)
        if date is None:                                                # 日付がNoneだったら
            date = datetime.date.today().strftime("%Y/%m/%d")           # 今日の文字列

        sql = f"SELECT * FROM light WHERE date='{date}' ORDER BY datetime ASC"
        df = pd.read_sql_query(sql, conn)                               # sql実行しpandas形式で格納する
        conn.close()
        return df


    def set_LED(self, value):
        """
        LED状態をDBに追加する
        Args:
            value: オン=1/ オフ=0
        Returns:
            imgB64: デイリーグラフの画像
        """
        # DBに登録する
        conn = sqlite3.connect(self.dbname)
        cur = conn.cursor()
        dt_now = datetime.datetime.now()                                # 今
        strdate = dt_now.strftime("%Y/%m/%d")                           # 日付
        strdt = dt_now.strftime("%Y/%m/%d %H:%M")                       # 日時
        sql = f"INSERT INTO light VALUES('{strdate}','{strdt}', '{value}')"
        cur.execute(sql)
        conn.commit()
        cur.close()
        conn.close()
        self.set_LED_summary(strdate)
        strB64 = db.make_daily_light_graph(strdate)
        return strB64


    def set_LED_summary(self, date):
        """
        点灯時間のサマリーデータを登録する
        Args:
            date: 日付（文字列）
        """
        dt_0 = str2datetime(f"{date} 00:00")                            # 指定した日の00:00のdatetime
        dt_24 = str2datetime(f"{date} 23:59")                           # 指定した日の23:59のdatetime
        summary_exists = self.exists("summary", date)                   # サマリーにその日のデータがあるか
        led_exists = self.exists("LED", date)                           # LEDテーブルにその日のデータがあるか
        if led_exists:                                                  # LEDテーブルにその日のデータがあるならば
            df = self.get_LED(date)                                     # その日のLEDデータを取得する
            df["datetime"] = pd.to_datetime(df["datetime"])             # 文字列の日時をdatetimeに変換する
            x = df["datetime"].to_list()                                # 時刻をリストにする
            x.append(dt_24)                                             # 23:59を追加
            y = df["value"].tolist()                                    # 値をリストにする
            y.append(0)                                                 # 0を追加
            lighting_minutes = 0                                        # 累計時間初期値
            last_value = 0                                              # 最初はオフ
            last_dt = dt_0                                              # 最初は00:00
            for dt, value in zip(x, y):                                 # xとyの各要素について
                if not last_value and value:                            # オフからオンになったら
                    last_dt = dt                                        # その時刻を覚えておく
                elif last_value and not value:                          # オンからオフになったら
                    timedelta = (dt - last_dt).total_seconds()          # オンになった時刻からの時間差を秒で求める
                    lighting_minutes += int((timedelta + 5)/60)         # 念のため+5秒した上で分にして累計にプラスする
                last_value = value                                      # 次の値と比較するためこの値を覚えておく

            if summary_exists:                                          # サマリーにその日のデータがあれば更新する
                sql = f"UPDATE summary"\
                        f" SET lighting_minutes={lighting_minutes}"\
                        f" WHERE date='{date}'"
            else:                                                       # データがなければ追加挿入する
                sql = f"INSERT INTO summary(date, lighting_minutes)"\
                        f" VALUES('{date}', {lighting_minutes})"
            conn = sqlite3.connect(self.dbname)
            cur = conn.cursor()
            cur.execute(sql)
            conn.commit()
            cur.close()
            conn.close()


    def make_daily_light_graph(self, date=None):
        """
        LED点灯状態のデイリーグラフを作成する
        Args:
            date: 日付（テキスト） Noneならば今日
        Returns:
            imgB64: デイリーグラフの画像
        """
        today = datetime.date.today().strftime("%Y/%m/%d")              # 今日の文字列
        if date is None:                                                # 日付がNoneだったら
            date = today                                                # 今日の文字列
        # 指定した日のサマリーデータ取得する
        conn = sqlite3.connect(self.dbname)
        cur = conn.cursor()
        sql = f"SELECT sunrise_time, sunset_time FROM summary WHERE date='{date}'"
        cur.execute(sql)
        result = cur.fetchall()[0]
        cur.close()
        conn.close()
        sunrise_time, sunset_time = result                              # 日の出、日の入り
        dt_sunrise = str2datetime(f"{date} {sunrise_time}")             # 日の出時刻のdatetime
        dt_sunset = str2datetime(f"{date} {sunset_time}")               # 日の入り時刻のdatetime
        dt_now = datetime.datetime.now()                                # 現在時刻のdatetime
        dt_0 = str2datetime(f"{date} 00:00")                            # 指定した日の00:00のdatetime
        dt_24 = str2datetime(f"{date} 23:59")                           # 指定した日の23:59のdatetime
        df = self.get_LED(date)                                         # 点灯データ取得する
        df["datetime"] = pd.to_datetime(df["datetime"])                 # 日時を文字列からdatetimeにする
        
        # グラフデータ作成
        x, y = [dt_0], [0]                                              # xとyの初期値 0:00に点灯オフ
        for dt, value in zip(df["datetime"], df["value"]):              # 各行について
            if value == y[-1]:                                          # 値が一つ前と同じならば
                pass                                                    # グラフ的には変化ないので何もしない
            else:                                                       # 値が変化していたら
                x.extend([dt, dt])                                      # yの値が変化するようxの値を2個追加
                y.extend([y[-1], value])                                # yの値を変化前と変化後で2個追加
        if date == today:                                               # 今日ならば
            if value:                                                   # 点灯オンならば
                x.extend([dt_now, dt_now])                              # yの値が変化するよう現在時刻を2個追加
                y.extend([1, 0])                                        # 集計のため一時的にオンからオフにする
            else:                                                       # 点灯オフならば
                x.append(dt)                                            # 現在時刻を追加
                y.append(0)                                             # 0（点灯オフ）を追加
        else:                                                           # 今日でなければ
            x.append(dt_24)                                             # 最後に23:59を追加
            y.append(0)                                                 # 最後に0（点灯オフ）を追加
        
        # 累計点灯時間
        lighting_minutes = 0                                            # 累計時間初期値
        last_value = False                                              # 最初はオフ
        last_dt = dt_0                                                  # 最初は00:00
        for dt, value in zip(x, y):                                     # xとyの各要素について
            if not last_value and value:                                # オフからオンになったら
                last_dt = dt                                            # その時刻を覚えておく
            elif last_value and not value:                              # オンからオフになったら
                timedelta = (dt - last_dt).total_seconds()              # オンになった時刻からの時間差を秒で求める
                lighting_minutes += int((timedelta + 5)/60)             # 分にして累計にプラスする（念のために+5秒してから）
            last_value = value                                          # 次の値と比較するためこの値を覚えておく
        conn = sqlite3.connect(self.dbname)
        cur = conn.cursor()
        sql = f"UPDATE summary"\
                f" SET lighting_minutes={lighting_minutes}"\
                f" WHERE date='{date}'"
        cur.execute(sql)                                                # 累計点灯時間をサマリーに登録する
        conn.commit()
        cur.close()
        conn.close()

        # グラフ描画
        width_px, height_px = 900, 200                                  # ピクセルでのサイズ
        width_in, height_in = width_px/self.dpi, height_px/self.dpi     # インチでのサイズ（整数でなくてもよい）
        fig, ax = plt.subplots(figsize=(width_in, height_in))
        ax.spines["right"].set_visible(False)
        ax.spines["top"].set_visible(False)
        ax.set_xlim(dt_0, dt_24)                                        # x軸の範囲
        ax.set_ylim(0, 1)                                               # y軸の範囲
        locator = mdates.AutoDateLocator()
        locator.intervald["HOURLY"] = 3                                 # x軸 3時間ごとに目盛表記
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H"))        # x軸の書式
        ax.fill_between(x, y, "-", linewidth=2, color="orange")         # プロット y軸との間塗りつぶし
        ax.vlines(dt_now, 0, 1, "RED")                                  # 現在時刻に赤線
        ax.set_title(f"{date}の点灯時間 合計{lighting_minutes}分")      # タイトル
        ax.axvspan(dt_0, dt_sunrise, color="gray", alpha=0.3)           # 夜の背景
        ax.axvspan(dt_sunset, dt_24, color="gray", alpha=0.3)           # 夜の背景
        fig.tight_layout()
        fig.canvas.draw()
        imgB64 = fig2str64(fig)
        return imgB64


    def get_summary_table(self, cumsum_date, date=None, days=7):
        """
        サマリーを取得する
        Args:
            cumsum_date: 累計の始点
            date    : 日付（文字列）未指定ならば今日
            days    : 何日前までか
        Return:
            dict    : サマリー辞書
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
                f" WHERE date BETWEEN '{cumsum_date}' AND '{date_to}'"\
                f" ORDER BY date ASC"
        df_sunlight = pd.read_sql_query(sql, conn)                      # LED点灯時間のみのデータフレーム
        df_sunlight = df_sunlight.set_index("date")                     # date列をインデックスに設定する
        df_sunlight = df_sunlight.sort_index()                          # インデックスでソートする
        df_sunlight = df_sunlight.cumsum()                              # 各日のデータを累積和にする
        df_sunlight = df_sunlight.rename(columns={"lighting_minutes": "lighting_minutes_sum"})      # 列名変更

        # 温度の集計
        sql = f"SELECT date, mean_temp FROM summary WHERE date BETWEEN '{cumsum_date}' AND '{date_to}'"
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
        return dict





















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

    def get_summary_graph(self, cumsum_date, date=None, days=7):
        """
        サマリーを取得する
        Args:
            cumsum_date: 累計の始点
            date_to: 日付（文字列）Noneならば今日
            days   : 何日前までか
        Return:
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
                f" WHERE date BETWEEN '{cumsum_date}' AND '{date_to}'"\
                f" ORDER BY date ASC"
        df_sunlight = pd.read_sql_query(sql, conn)                      # LED点灯時間のみのデータフレーム
        df_sunlight = df_sunlight.set_index("date")                     # date列をインデックスに設定する
        df_sunlight = df_sunlight.sort_index()                          # インデックスでソートする
        df_sunlight = df_sunlight.cumsum()                              # 各日のデータを累積和にする
        df_sunlight = df_sunlight.rename(columns={"lighting_minutes": "lighting_minutes_sum"})      # 列名変更

        # 温度の集計
        sql = f"SELECT date, mean_temp FROM summary WHERE date BETWEEN '{cumsum_date}' AND '{date_to}'"
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
        width_px, height_px = 900, 200                                  # ピクセルでのサイズ
        width_in = width_px/self.dpi                                    # インチでのサイズ（整数でなくてもよい）
        height_in = height_px/self.dpi
        x = [key[5:] for key in dict.keys()]                            # yyyy/mm/dd から yy/dd にしてx軸とする

        # 温度のグラフ
        fig, ax = plt.subplots(figsize=(width_in, height_in))
        ax.spines["right"].set_visible(False)
        ax.spines["top"].set_visible(False)
        y_max = [item["max_temp"] for item in dict.values()]
        y_min = [item["min_temp"] for item in dict.values()]
        y_mean = [item["mean_temp"] for item in dict.values()]
        ax.plot(x, y_max, ":b", linewidth=1)
        ax.plot(x, y_min, ":b", linewidth=1)
        ax.plot(x, y_mean, ".-b", linewidth=2)
        ax.set_title("最高・最低・平均気温（度）")
        fig.tight_layout()
        for i, value in enumerate(y_mean):
            ax.text(x[i], y_mean[i]+ 2, value)
            fig.canvas.draw()
        temp_b64 = fig2str64(fig)

        # 点灯時間のグラフ
        fig, ax = plt.subplots(figsize=(width_in, height_in))
        ax.spines["right"].set_visible(False)
        ax.spines["top"].set_visible(False)
        y = [item["lighting_minutes"] for item in dict.values()]
        ax.plot(x, y, ".-", linewidth=2, color="orange")
        ax.set_title("日当たりのLED点灯時間（分）")
        fig.tight_layout()
        for i, value in enumerate(y):
            ax.text(x[i], y[i]+ 2, value)
            fig.canvas.draw()
        light_b64 = fig2str64(fig)
        return light_b64, temp_b64




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





    def set_LED_old(self, minute):
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


    def draw_dailygraph(self, date=None):
        """
        デイリーグラフ
        Args:
            date: 日付（文字列）Noneならば今日
        Returns:
            lightB64
            tempB64
        """
        dt_now = datetime.datetime.now()
        if date is None:                                                # 日付がNoneだったら
            date = datetime.date.today().strftime("%Y/%m/%d")           # 今日の文字列
        lightB64 = self.make_daily_light_graph(date)
        tempB64 = self.make_daily_temp_graph(date)
        return lightB64, tempB64


def fig2str64(fig):
    # matplotlib.pyplotの画像をBase64の画像に変換する
    img = np.array(fig.canvas.renderer.buffer_rgba())           # numpy配列にする
    img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)                 # OpenCV画像にする
    #cv2.imshow("graph", img)
    #cv2.waitKey(0)
    #cv2.destroyAllWindows()
    _, imgEnc = cv2.imencode(".jpg", img)                       # メモリ上にエンコード
    imgB64 = base64.b64encode(imgEnc)                           # base64にエンコード
    strB64 = "data:image/jpg;base64," + str(imgB64, "utf-8")    # 文字列化
    return strB64

def str2datetime(str):
    # 文字列をdatetimeに変換する
    return datetime.datetime.strptime(str, "%Y/%m/%d %H:%M")


db = DB()

def main():
    ret = db.set_LED(1)
    ret = db.set_temperature(10, 20)
    pass

if __name__ == "__main__":
    main()

