from flask import Flask, render_template, request
from myEphem import Ephem
# from myContec import Contec
from myDatabase import DB
import json
import random
from time import sleep
import datetime
import configparser
import os
import subprocess as sp
import numpy as np

"""
import RPi.GPIO as GPIO
import dht11

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.cleanup()

humi_pin = 14
led_pin = 16
pilot_pin = 21
pilot_status = False
humi_sensor = dht11.DHT11(pin=humi_pin)
"""

# グローバル変数
light_sum = 0               # 光センサーオフの累計
sensing_count = 1           # 光センサー計測リセット回数
light_cnt = 0               # 光センサー計測回数　sensing_countの回数でリセット
daily_date = datetime.date.today().strftime("%Y/%m/%d")           # 今日の文字列

# 日時を文字列として返す
def getTime():
    dt = datetime.datetime.now()
    return dt.strftime("%Y/%m/%d %H:%M:%S")


"""
contec = Contec()                   # コンテックのクラス
"""
db = DB()                           # データベースのクラス

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/writeDB", methods = ["POST"])
def writeDB():
    if request.method == "POST":
        table = request.form["table"]
        values = int(request.form["values"])
        if table == "LED":
            db.set_LED(values)
        return json.dumps({"result": "OK"})


# サマリーテーブル
@app.route("/getSummaryTable", methods=["POST"])
def getSummaryTable():
    if request.method == "POST":
        # サマリー取得
        cumsum_date = db.cumsum_date
        dict = db.get_summary_table(cumsum_date)
        html = f"<b>日々の実績　および　{cumsum_date} からの累計</b>"\
                "<table><tr><td class='center'>日付</td><td class='right'>点灯時間</td><td class='right'>時間累計</td>"\
                "<td class='right'>平均温度</td><td class='right'>温度累計</td></tr>"
        for key, item in dict.items():
            html += f"<tr><td>{key}</td>"\
                    f"<td class='right w1'>{item['lighting_minutes']}分</td><td class='right w1'>{item['lighting_minutes_sum']}分</td></td>"\
                    f"<td class='right w1'>{item['mean_temp']}度</td><td class='right w1'>{item['mean_temp_sum']}度</td></td>"
        html += "</table>"
        result = {"html": html}
        return json.dumps(result)


# サマリーグラフ
@app.route("/showSummaryGraph", methods=["POST"])
def showSummaryGraph():
    if request.method == "POST":
        # サマリー取得
        cumsum_date = db.cumsum_date
        light_b64, temp_b64 = db.get_summary_graph(cumsum_date)
        result = {"light_b64":light_b64, "temp_b64":temp_b64}
        return json.dumps(result)


# 一日グラフ
@app.route("/showDairyGraph", methods=["POST"])
def showDairyGraph():
    if request.method == "POST":
        light_b64, temp_b64 = db.draw_dailygraph(daily_date)
        result = {"light_b64":light_b64, "temp_b64":temp_b64}
        return json.dumps(result)


# 暦
@app.route("/getEphem", methods = ["POST"])
def getEphem():
    try:
        ephem = Ephem(db.ephem_config)              # 設定をもとにephemを作成する
        dict = ephem.get_data()                     # データを辞書として取得する
        db.set_ephem(dict)
    except Exception as e:
        message = str(e)
        dict = {"error": message}                   # エラーメッセージ
    return json.dumps(dict)                         # 辞書をJSONにして返す


# 温湿度計
@app.route("/getHumi", methods=["POST"])
def getHumi():
    if request.method == "POST":
        is_try = request.form["isTry"]
        if is_try=="true":                          # トライならば
            temp = random.randint(30, 60)
            humi = random.randint(60, 90)
        else:                                       # 本番ならば
            print("本番")
            for i in range(10):                     # センサー値取得失敗するかもしれないので10回ループする
                result = humi_sensor.read()
                if result.is_valid():                   # センサー値取得できたら
                    temp = round(result.temperature, 1) # 温度 小数第一位まで
                    humi = round(result.humidity, 1)    # 湿度 小数第一位まで
                    break                               # ループから抜ける
                else:                                   # 10回ループしても駄目なら
                    temp = -1
                    humi = -1                           # ありえない値を湿度に登録する
        imgB64 = db.set_temperature(temp, humi)
        dict = {"temp": temp,
                "humi": humi,
                "imgB64": imgB64}
        return json.dumps(dict)


# 育成LED（コンテック）への出力
@app.route("/enpowerLED", methods=["POST"])
def enpowerLED():
    if request.method == "POST":
        is_On = int(request.form["isOn"])
        is_try = request.form["isTry"]
        print("is_On=" , is_On)
        imgB64 = db.set_LED(is_On)
        if is_On:
            # print("育成LEDオン")
            if is_try != "true":                    # 本番ならば
                contec.output(True)
            pass
        else:
            # print("育成LEDオフ")
            if is_try != "true":                    # 本番ならば
                contec.output(False)
            pass
        return json.dumps({"imgB64": imgB64})


# 設定DB 読み込み
@app.route("/getConfig", methods=["POST"])
def getConfig():
    global sensing_count
    if request.method == "POST":
        dict = db.get_config()                              # データベースから設定を読み込む
        # コンテックの設定はリストにして登録する
        arr = []
        for i in [1, 2, 3, 4]:
            arr.append(int(dict[f"output{i}"]))
#        contec.define_output_relays(arr)
        sensing_count = int(dict["sensing_count"])
        return json.dumps(dict)

# 設定DB 書き込み
@app.route("/setConfig", methods=["POST"])
def setConfig():
    global light_cnt
    if request.method == "POST":
        dict = {"place": request.form["place"],
                "lat": request.form["lat"],
                "lon": request.form["lon"],
                "elev": request.form["elev"],
                "morning_offset": request.form["morning_offset"],
                "evening_offset": request.form["evening_offset"],
                "morning_minutes": request.form["morning_minutes"],
                "evening_minutes": request.form["evening_minutes"],
                "sensing_interval": request.form["sensing_interval"],
                "sensing_count": request.form["sensing_count"],
                "output1": request.form["output1"],
                "output2": request.form["output2"],
                "output3": request.form["output3"],
                "output4": request.form["output4"],
                "batt_yellow": request.form["batt_yellow"],
                "batt_green": request.form["batt_green"],
                "cumsum_date": request.form["cumsum_date"],
                "isHumiTry": request.form["isHumiTry"],
                "isContecTry": request.form["isContecTry"],
                "isLEDTry": request.form["isLEDTry"],
                "isNightSense": request.form["isNightSense"],
                }
        db.set_config(dict)
        
        # コンテックリレー出力設定を変更する
        arr = []
        for i in [1,2,3,4]:
            key = f"output{i}"
            arr.append(int(request.form[key]))      # 1/0 をリストに追記していく
        """
        contec.define_output_relays(arr)
        """
        light_cnt = 0                               # 設定変更したら光センサー取得カウントをリセットする
        return json.dumps({"response": "done"})

# DB削除
@app.route("/delDB", methods=["POST"])
def delDB():
    if request.method == "POST":
        del_date = request.form["date"]
        db.delete(del_date)
    return json.dumps({"result":"OK"})


# コンテック（光センサー＋バッテリー）
@app.route("/getContec", methods=["POST"])
def getContec():
    global light_cnt, light_sum, light_log, sensing_count
    if request.method == "POST":
        is_try = request.form["isTry"]
        is_light_cnt = request.form["isLightCnt"]
        if is_light_cnt == "true":
            light_cnt = (light_cnt+1) % sensing_count
            if light_cnt == 0:
                light_log = ""
                light_sum = 0
        inputs = []                                         # コンテックの戻り値の初期値
        if is_try=="true":                                  # トライならば
            for _ in range(8):
                inputs.append(random.choice([1, 0]))
        else:                                               # 本番ならば
            inputs = contec.input()
            print("コンテック　本番", inputs)
            pass

        # コンテックの結果を光センサーの結果と電圧リレーの結果に分ける
        lights = inputs[:5]
        volts = inputs[5:]

        log = ""
        for input in inputs:
            log += "○" if input==1 else "−"

        # 光センサーの積算
        if is_light_cnt == "true":          # 光センサーの状態を積算する設定ならば
            light_sum += sum(lights)        # 光の合計を加算する
        dict = {}
        dict["light_sum"] = light_sum
        dict["log"] = log
        dict["light_cnt"] = light_cnt

        # 電圧リレーの計算
        relay1, relay2, _ = volts           # リレー1=緑信号（低圧）　リレー2=青信号（高圧）　
        if relay2:                          # リレー2がオンならば
            dict["volt"] = "青"             # 「青」
        elif relay1:                        # リレー2がオフでリレー1がオンならば
            dict["volt"] = "緑"             # 「緑」
        else:                               # いずれでもなければ
            dict["volt"] = "黄"             # 「黄」

        return json.dumps(dict)


# OSの時刻を設定する
@app.route("/setClock", methods=["POST"])
def setClock():
    if request.method == "POST":
        set_time = request.form["set_time"] # 設定する日時
        cmd = f"sudo date {set_time}"       # linuxのコマンド
        sp.Popen(cmd.split())               # 空白で区切ってリストにし、実行する
        return json.dumps({"response": "done"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
    # app.run(debug=True)
