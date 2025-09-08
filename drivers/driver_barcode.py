import ctypes
import win32gui
import win32process
import win32con
from pynput import keyboard

class DriverBarcode:
    def __init__(self):
        self.scanned_code = ""
        self.set_keyboard_language(0x0407)  # Optional: set to German layout

    def scan_barcode(self):
        """Read barcode and wait until Enter is pressed."""
        self.scanned_code = ""
        with keyboard.Listener(on_press=self.on_key_press) as listener:
            listener.join()  # This ensures it waits for input
            return self.scanned_code  # Return the scanned barcode

    def on_key_press(self, key):
        """Event handler for keyboard input in HID mode."""
        try:
            if key.char:
                self.scanned_code += key.char  # Append character to barcode string
        except AttributeError:
            if key == keyboard.Key.enter:  # Barcode scanners send Enter after scan
                #print(f"[SUCCESS] Scanned Barcode: {self.scanned_code}")
                return False  # Stop listener

    def set_keyboard_language(self, lang_id):
        """Set keyboard language to a specific layout (default: German)."""
        hwnd = win32gui.GetForegroundWindow()
        thread_id, _ = win32process.GetWindowThreadProcessId(hwnd)
        ctypes.windll.user32.PostThreadMessageW(thread_id, win32con.WM_INPUTLANGCHANGEREQUEST, 0, lang_id)
