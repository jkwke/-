import win32gui

def move_window():
    hwnd = win32gui.FindWindow("MainWindow", "植物大战僵尸中文版")
    win32gui.MoveWindow(hwnd, 405, 174, 403, 326, True)

move_window()

