import tkinter as tk


def key_image(parent, level):
    image = tk.PhotoImage(master=parent, width=59, height=25)
    image.put("#181c20", to=(0, 0, 59, 25))
    for index in range(5):
        image.put("#34d17b" if index < level else "#343b42", to=(index * 12, 1, index * 12 + 9, 24))
    return image
