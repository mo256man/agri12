# coding: utf-8
import ctypes
import sys
import cdio
import time
import datetime

class Contec():
    def __init__(self):
        print("start")
        self.DEV_NAME = "DIO000"                            # デバイス名
        self.port_no = ctypes.c_short(0)                    # ポートNo
        # input_pins = [1, 2, 3, 4, 5]		                # 光センサーが接続されているコンテックの入力コネクタのピン番号
        input_pins = [1, 2, 3, 4, 5, 6, 7, 8]		        # コンテックの入力コネクタのピン番号
        output_pins = [1, 2, 3, 4]                          # コンテックの出力コネクタのピン番号

        self.dio_id = ctypes.c_short()
        self.io_data = ctypes.c_ubyte()
        self.bit_no = ctypes.c_short()
        self.err_str = ctypes.create_string_buffer(256)

        self.input_bits = [8-pin for pin in input_pins]     # 入力コネクタのピンのビット
        self.output_bits = [8-pin for pin in output_pins]   # 出力コネクタのピンのビット

        self.lights = []                                    # インプットの状態（初期値）
        self.relays = [1, 1, 1, 1]                          # 4個のリレーへの出力（初期値＝全出力）

        # ドライバ初期化
        ret = cdio.DioInit(self.DEV_NAME.encode(), ctypes.byref(self.dio_id))
        if ret != cdio.DIO_ERR_SUCCESS:
            cdio.DioGetErrorString(ret, self.err_str)
            print(f"DioInit = {ret}: {self.err_str.value.decode('utf-8')}")
            sys.exit()

    def num2array(self, num):
        # """8ビットの入力データを光センサーオンオフのリストとして返す"""
        result = []
        for bit in self.input_bits:
            ans = 1 if num & (1 << bit) else 0	            # 1をbit回ビットシフトした値との論理積を取り、0以外なら1を、0なら0を返す
            result.append(ans)
        print("インプットの状態　" , result)
        return result

    def array2num(self, arr):
        # """リストを8ビットの数値として返す"""
        result = 0
        for value, bit in zip(arr, self.output_bits):
            result += value * 2**bit
        return result

    def input(self):
        print("contec input start")
        ret = cdio.DioInpByte(self.dio_id, self.port_no, ctypes.byref(self.io_data))
        if ret == cdio.DIO_ERR_SUCCESS:
            arr = self.num2array(self.io_data.value)
            return arr
        else:
            cdio.DioGetErrorString(ret, self.err_str)
            print(f"DioInpByte = {ret}: {self.err_str.value.decode('utf-8')}")
            return []

    def output(self, bool):
        num = self.array2num(self.relays)
        io_data = ctypes.c_ubyte(num) if bool else ctypes.c_ubyte(0)
        ret = cdio.DioOutByte(self.dio_id, self.port_no, io_data)
        if ret == cdio.DIO_ERR_SUCCESS:
            cdio.DioGetErrorString(ret, self.err_str)
            print(f'DioOutByte port = {self.port_no.value}: data = 0x{io_data.value:02x}')
        else:
            cdio.DioGetErrorString(ret, self.err_str)
            print(f"DioOutByte = {ret}: {self.err_str.value.decode('utf-8')}")
    
    def define_output_relays(self, array):
        self.relays = array

contec = Contec()

def main():
    while True:
        input_array = contec.input()
        print(f"{datetime.datetime.now().strftime('%H:%M:%S')}")
        for i, bit in enumerate(input_array):
            ans = "off" if bit else "on"
            print(f"{i+1}番のインプット: {ans}")

        light_cnt = sum(input_array)
        if light_cnt > 2:
            print("暗いので点灯")
            contec.output(True)
        else:
            print("明るいので消灯")
            contec.output(False)
        time.sleep(1)
        

if __name__ == "__main__":
    main()
