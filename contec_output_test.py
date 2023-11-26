import ctypes
import sys
import cdio
import time
import datetime

def main():
    dio_id = ctypes.c_short()
    io_data = ctypes.c_ubyte()
    port_no = ctypes.c_short()
    bit_no = ctypes.c_short()
    err_str = ctypes.create_string_buffer(256)

    # ドライバ初期化
    DEV_NAME = "DIO000"
    lret = cdio.DioInit(DEV_NAME.encode(), ctypes.byref(dio_id))
    port_no = ctypes.c_short(0)
    if lret != cdio.DIO_ERR_SUCCESS:
        cdio.DioGetErrorString(lret, err_str)
        print(f"DioInit = {lret}: {err_str.value.decode('utf-8')}")
        sys.exit()
 
    # メインループ
    try:
        for i in range(0, 255, 16):
#        while True:
            #buf = 0b10101010
            #buf = 0x00
            buf = 255 - i
            io_data = ctypes.c_ubyte(buf)
            lret = cdio.DioOutByte(dio_id, port_no, io_data)
            if lret == cdio.DIO_ERR_SUCCESS:
                cdio.DioGetErrorString(lret, err_str)
                print(f"{datetime.datetime.now().strftime('%H:%M:%S')} : 0x{io_data.value:02x}, 0b{format(io_data.value, '08b')}")
            else:
                cdio.DioGetErrorString(lret, err_str)
                print(f"DioOutByte = {lret}: {err_str.value.decode('utf-8')}")            
            time.sleep(1)
#            lret = cdio.DioOutByte(dio_id, port_no, 0)
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n終了")
        lret = cdio.DioOutByte(dio_id, port_no, 0)
        # ドライバ終了
        lret = cdio.DioExit(dio_id)
        if lret != cdio.DIO_ERR_SUCCESS:
            cdio.DioGetErrorString(lret, err_str)
            print(f"DioExit = {lret}: {err_str.value.decode('utf-8')}")
        # プログラム終了
        time.sleep(3)
        sys.exit()

if __name__ == "__main__":
    main()
