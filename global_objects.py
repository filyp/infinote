import tkinter as tk

import pynvim

nvim = pynvim.attach("child", argv=["/usr/bin/env", "nvim", "--embed", "--headless"])

root = tk.Tk()
root.configure(bg="black")
root.geometry("1000x1000")
# root.attributes("-fullscreen", True)

nodes = []
