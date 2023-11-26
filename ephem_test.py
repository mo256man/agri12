import ephem

# 観測者の情報を設定（例: 東京の緯度と経度）
observer = ephem.Observer()
observer.lat = '35.682839'
observer.lon = '139.759455'

# 月の位相を計算
moon_phase = ephem.Moon(observer).phase
print(moon_phase)

# 月の位相を度数に変換
moon_phase = moon_phase *14/100
print(moon_phase)
