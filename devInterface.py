import os
import sys
from tkinter import Tk, Button
from enum import Enum, auto
import threading


class STYLE(Enum):
    DEFAULT = auto()
    WARNING = auto()
    DANGER = auto()


class TGBotInterface:
    def __init__(self):
        pass

    def _build(self):
        self.root = Tk()
        self.root.title("Dev Console")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        #Button(self.root, text="🔄 Reload Bot", command=self.reload).pack(padx=10, pady=5)
        Button(self.root, text="❌ Exit", command=self.close).pack(padx=10, pady=5)

    def close(self):
        self.root.destroy()
        if self.ON_KILL:
            self.ON_KILL()
        os._exit(0)

    def reload(self):
        python = sys.executable
        self.root.destroy()
        os.execv(python, [python] + sys.argv)

    def _start(self):
        self._build()
        self.root.mainloop()

    def start(self,onKill):
        self.ON_KILL = onKill
        threading.Thread(target=self._start, daemon=True).start()
