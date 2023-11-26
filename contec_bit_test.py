# coding: utf-8

output_pins = [1, 2, 3, 4]                          # リレーが接続されているコンテックの出力コネクタのピン番号
output_values = [0, 1, 0, 1]						# 各リレーを出力するかしないか
output_bits = [8-pin for pin in output_pins]   		# リレーが接続されているコンテックの出力コネクタのピンのビット

print(output_values)
print(output_bits)

result = 0
for value, bit in zip(output_values, output_bits):
	result += value * 2**bit
	
print(result)
