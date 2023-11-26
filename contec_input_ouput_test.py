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
        input_pins = [1, 2, 3, 4, 5]		                # 光センサーが接続されているコンテックの入力コネクタのピン番号
        output_pins = [1, 2, 3, 4]                          # リレーが接続されているコンテックの出力コネクタのピン番号

        self.dio_id = ctypes.c_short()
        self.io_data = ctypes.c_ubyte()
        self.bit_no = ctypes.c_short()
        self.err_str = ctypes.create_string_buffer(256)

        self.input_bits = [8-pin for pin in input_pins]     # 光センサーが接続されているコンテックの入力コネクタのピンのビット
        self.output_bits = [8-pin for pin in output_pins]   # リレーが接続されているコンテックの出力コネクタのピンのビット
        
        self.lights = []                                    # 5個の光センサーの状態（の初期値）
        self.relays = [1, 1, 1, 1]                          # 4個のリレーへの出力（全出力）

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
        return result

    def input(self):
        ret = cdio.DioInpByte(self.dio_id, self.port_no, ctypes.byref(self.io_data))
        if ret == cdio.DIO_ERR_SUCCESS:
            arr = self.num2array(self.io_data.value)
            return arr
        else:
            cdio.DioGetErrorString(lret, err_str)
            print(f"DioInpByte = {lret}: {err_str.value.decode('utf-8')}")
            return []

    def output(self, bool):
        io_data = ctypes.c_ubyte(255) if bool else ctypes.c_ubyte(0)
        ret = cdio.DioOutByte(self.dio_id, self.port_no, io_data)
        if ret == cdio.DIO_ERR_SUCCESS:
            cdio.DioGetErrorString(ret, self.err_str)
            print(f'DioOutByte port = {self.port_no.value}: data = 0x{io_data.value:02x}')
        else:
            cdio.DioGetErrorString(lret, err_str)
            print(f"DioOutByte = {lret}: {err_str.value.decode('utf-8')}")        

def light_on(bool):
    dio_id = ctypes.c_short()
    io_data = ctypes.c_ubyte()
    port_no = ctypes.c_short()
    bit_no = ctypes.c_short()
    err_str = ctypes.create_string_buffer(256)
    DEV_NAME = "DIO000"
    port_no = ctypes.c_short(0)
    lret = cdio.DioInit(DEV_NAME.encode(), ctypes.byref(dio_id))

    buf = 0x10000000 if bool else 0b00000000
    io_data = ctypes.c_ubyte(buf)
    lret = cdio.DioOutByte(dio_id, port_no, io_data)
    if lret == cdio.DIO_ERR_SUCCESS:
        cdio.DioGetErrorString(lret, err_str)
        print(f"{datetime.datetime.now().strftime('%H:%M:%S')} : 0x{io_data.value:02x}, 0b{format(io_data.value, '08b')}")
    else:
        cdio.DioGetErrorString(lret, err_str)
        print(f"DioOutByte = {lret}: {err_str.value.decode('utf-8')}")            


contec = Contec()

def main():
    while True:
        input_array = contec.input()
        print(f"{datetime.datetime.now().strftime('%H:%M:%S')}")
        for i, bit in enumerate(input_array):
            ans = "off" if bit else "on"
            print(f"{i+1}番の光センサー: {ans}")

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
