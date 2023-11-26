import ephem
import datetime
import numpy as np
import cv2
import math
import base64

class Ephem():
    def __init__(self, dict, isB64=True):
        self.place = dict["place"]
        lat = dict["lat"]
        lon = dict["lon"]
        elev = int(dict["elev"])
        self.isB64 = isB64                              # デバッグ時、FalseにするとBase64でなくOpenCVになる

        self.observer = ephem.Observer()
        self.observer.lat = str(lat)
        self.observer.lon = str(lon)
        self.observer.elev = elev


    def get_data(self):
        dt = datetime.date.today()              # ローカル日付
        tz = datetime.timedelta(hours=+9)       # 日本とUTCの時差

        # 日の出と日没の時刻を計算
        self.observer.date = dt
        sunrise = self.observer.next_rising(ephem.Sun()).datetime() + tz
        sunset = self.observer.next_setting(ephem.Sun()).datetime() + tz

        # 月齢はその日の正午で計算する
        dt_12h = datetime.datetime(dt.year, dt.month, dt.day, 12-9, 0, 0, 0)  # 12時（時差を考慮）
        self.observer.date = dt_12h
        moon_phase =round(self.observer.date - ephem.previous_new_moon(self.observer.date),2)
        dict = {"sunrise_time": datetime.datetime.strftime(sunrise, "%H:%M"),
                "sunset_time": datetime.datetime.strftime(sunset, "%H:%M"),
                "moon_phase": moon_phase,
                "moon_image": self.draw_moon(moon_phase, self.isB64)
                }
        return dict

    def epdate2str(self, epdate):
        return (epdate)

    def draw_moon(self, age, isB64):
        TRANS = (0,0,0,0)                                       # 透明色
        YELLOW = (100,255,255,255)                              # 黄色
        GRAY = (60,60,60,255)                                   # 灰色
        SIZE = 100                                              # 画像サイズ
        xc, yc = SIZE//2, SIZE//2                               # 満月の中心
        R = 46                                                  # 満月の半径

        img = np.full((SIZE, SIZE, 4), TRANS, np.uint8)         # 透明背景
        cv2.circle(img, (xc,yc), R, YELLOW, -1)                 # 満月を描く
        mask = img // YELLOW                                    # 黄色い満月を黄色で割る　つまり0と1からなるマスク

        pts = [(xc, yc-R-5), (xc-R-10,yc-R-5), (xc-R-10,yc+R+5), (xc, yc+R+5)]  # 塗りつぶしエリアの初期値
        a = 2 * math.pi * age / 28                              # 月齢を角度に直す（29.53日周期を28日周期にする）

        if age < 0.3 or age > 27.7:                             # 月齢0のとき
            cv2.circle(img, (xc,yc), R, GRAY, -1)               # 特別扱いする
        elif 13.4< age < 14.3:                                           # 月齢14のとき
            cv2.circle(img, (xc,yc), R, YELLOW, -1)             # 特別扱いする
        else:
            for t in range(0, 180, 5):                          # 0度（北極）から180度（南極）まで
                th = math.radians(t)                            # 度をラジアンに直す
                r = R * math.sin(th) * math.cos(a)              # その緯度における半径
                x = int(xc + r)                                 # x座標
                y = int(yc + R * math.cos(th))                  # y座標
                pts.append((x,y))                               # その座標を塗りつぶしエリア座標群に追加する
            cv2.fillConvexPoly(img, np.array(pts), GRAY)        # 塗りつぶしエリアを塗りつぶす

        img = (img * mask).astype(np.uint8)                     # 満月の外を透明色にする

        if isB64:                                               # B64フラグがONならば
            _, imgEnc = cv2.imencode(".png", img)               # メモリ上にエンコード
            imgB64 = base64.b64encode(imgEnc)                   # base64にエンコード
            strB64 = "data:image/png;base64," + str(imgB64, "utf-8")    # 文字列化
            return strB64                                       # そういう文字列を返す
        else:                                                   # さもなくば
            return img                                          # OpenCV画像を返す


if __name__=="__main__":
    # このコード単品で動かす際のサンプル　本番では使わない
    nagoya = {  "place": "名古屋",
                "lat": 35.1667,
                "lon": 136.9167,
                "elev": 0}

    ep = Ephem(nagoya, isB64=False)
    data = ep.get_data()
    print(data["today_rising"])
    print(data["today_setting"])
    print(data["moon_phase"])
    #cv2.imshow("moon", data["moon_image"])
    #cv2.waitKey(0)
    #cv2.destroyAllWindows()
    pass
