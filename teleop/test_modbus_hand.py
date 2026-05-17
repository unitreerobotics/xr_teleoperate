import multiprocessing
import time
from inspire_sdkpy import inspire_sdk, inspire_hand_defaut

def worker(ip,LR,name,network=None):
    handler=inspire_sdk.ModbusDataHandler(network=network,ip=ip, LR=LR, device_id=1)

    call_count = 0
    start_time = time.perf_counter()
    time.sleep(0.5)
    
    try:
        while True:
            data_dict = handler.read()
            call_count += 1
            time.sleep(0.001)
            
            if call_count % 10 == 0:
                elapsed_time = time.perf_counter() - start_time
                frequency = call_count / elapsed_time
                print(f"{name} 当前频率: {frequency:.2f} Hz, 调用次数: {call_count}, 耗时: {elapsed_time:.6f} 秒")
    except KeyboardInterrupt:
        elapsed_time = time.perf_counter() - start_time
        frequency = call_count / elapsed_time if elapsed_time > 0 else 0
        print(f"{name} 程序结束. 总调用次数: {call_count}, 总耗时: {elapsed_time:.6f} 秒, 最终频率: {frequency:.2f} Hz")

if __name__ == "__main__":
    # 使用默认IP地址的示例

    process_r = multiprocessing.Process(target=worker, args=('192.168.123.211','r',"右手进程"))
    process_l = multiprocessing.Process(target=worker, args=('192.168.123.210','l',"左手进程"))

    process_r.start()
    time.sleep(0.6)
    process_l.start()

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        process_r.terminate()
        process_l.terminate()
