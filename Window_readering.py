import ctypes.wintypes
import mmap
import time
import struct
import ctypes
from ctypes import wintypes

# 打开共享内存
shm = mmap.mmap(-1, 816, "PVZ_HOOK_SHARED_MEM")


class PvZReader:
    RECORD_SIZE = 16

    def __init__(self):
        self.hwnd = None
        self.h_proc = None
        self._init_game_handle()

    def _init_game_handle(self):
        """初始化游戏窗口句柄和进程句柄"""
        PROCESS_VM_READ = 0x0010
        self.hwnd = ctypes.windll.user32.FindWindowW("MainWindow", None)

        if not self.hwnd:
            print("未找到窗口")
            return False

        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(self.hwnd, ctypes.byref(pid))
        self.h_proc = ctypes.windll.kernel32.OpenProcess(PROCESS_VM_READ, False, pid)
        return True

    def read_dword(self, addr):
        buf = ctypes.create_string_buffer(4)
        read = ctypes.c_size_t(0)
        ctypes.windll.kernel32.ReadProcessMemory(
            self.h_proc, ctypes.c_void_p(addr), buf, 4, ctypes.byref(read)
        )
        return struct.unpack('<I', buf.raw)[0]

    def read_float(self, addr):
        buf = ctypes.create_string_buffer(4)
        read = ctypes.c_size_t(0)
        ctypes.windll.kernel32.ReadProcessMemory(
            self.h_proc, ctypes.c_void_p(addr), buf, 4, ctypes.byref(read)
        )
        return struct.unpack('<f', buf.raw)[0]

    def read_plant_CD(self):  # 返回的是第一个植物的CD
        one = self.read_dword(0x6A71A8)
        two = self.read_dword(one + 0x68)
        three = self.read_dword(two + 0x768)
        four = self.read_dword(three + 0x144)
        return four + 0x4C

    def get_mouse_state(self):  # 获取鼠标状态
        one = self.read_dword(0x6A79DC)
        two = self.read_dword(one + 0x68)
        three = self.read_dword(two + 0x88)
        four = self.read_dword(three + 0xC)
        five = self.read_dword(four + 0x138)
        return five + 0x28

    def get_sunlight(self):
        one = self.read_dword(0x6A9EC0)
        two = self.read_dword(one + 0x768)
        sun = self.read_dword(two + 0x5560)
        return sun

    def get_zombie_data(self, filter_x_max=800):
        if not self.h_proc:
            return []

        zombie_entries = []

        try:
            shm.seek(0)
            raw = shm.read(800)
            processed_bases = set()
            current_zombie_numbers = 0

            for i in range(50):
                offset = i * self.RECORD_SIZE
                sun, old_value, level_change, zombie_number = struct.unpack_from('<IIII', raw, offset)
                if old_value == 0:
                    continue
                else:
                    if old_value in processed_bases:
                        continue

                    processed_bases.add(old_value)
                    current_hp = self.read_dword(old_value)
                    head_hat = self.read_dword(old_value + 0x8)
                    zombie_x = self.read_float(old_value - 0x9C)
                    zombie_y = self.read_float(old_value - 0x98)
                    current_zombie_numbers = self.read_dword(zombie_number)

                    if current_hp == 0:
                        continue
                    else:
                        if filter_x_max is not None and zombie_x > filter_x_max:
                            continue

                        zombie_entries.append({
                            'sun': sun,
                            'base': old_value,
                            'hp': current_hp,
                            'head_hat': head_hat,
                            'count': current_zombie_numbers,
                            'level': level_change,
                            'x': zombie_x,
                            'y': zombie_y,

                        })

            return zombie_entries

        except Exception as e:
            print(f"读取数据时出错：{e}")
            return []

    def close(self):
        """关闭进程句柄"""
        if self.h_proc:
            ctypes.windll.kernel32.CloseHandle(self.h_proc)


def main(reader):
    zombie_entries = reader.get_zombie_data()

    if not zombie_entries:
        print("未获取到僵尸数据")
        return

    current_zombie_numbers = zombie_entries[0]['count'] if zombie_entries else 0
    max_print = min(len(zombie_entries), current_zombie_numbers) if current_zombie_numbers > 0 else 0

    if max_print > 0:
        entries_to_print = zombie_entries[-max_print:]
        for unit in entries_to_print:
            if unit['x'] > 800:
                continue
            row = int(unit['y'] // 100) + 1
            print(f"阳光：{unit['sun']}，僵尸：总 HP={unit['hp'] + unit['head_hat']}，"
                  f"数量={unit['count']}，"
                  f"x 位置={unit['x']:.0f}，y 位置={row}")

    print("-" * 25)


if __name__ == "__main__":
    reader = PvZReader()
    try:
        while True:
            main(reader)
            time.sleep(1)
    except KeyboardInterrupt:
        print("已退出")
    finally:
        reader.close()
