'''tedtoolkit.gui.image_viewer - a resizable, in-memory image gallery window (Prev/Next
navigation, "x of y" label). No existing GUI primitive in this codebase shows a persistent,
resizable window with live user interaction - g_sel_file()/g_sel_folder() etc. (dialogs.py) are
one-shot modal dialogs that return as soon as the user picks something. This is new territory,
added specifically for qr_encode()'s output_type='gui' path, but follows the same role those
dialogs play: it is a GUI primitive called BY a guided function's wrapper, not itself a
_check_assignment-guarded guided function, and it blocks (its own tkinter mainloop) until the
user closes the window, exactly like a modal dialog closing.
'''

# pylint: disable=no-member
# Image.LANCZOS is a real, verified-at-runtime constant; PIL's C-extension stubs aren't fully
# introspectable by pylint (a well-known Pillow/pylint false positive), not a defect.

import tkinter as tk

from PIL import Image, ImageTk


def g_show_image_gallery(images, **kwargs):
    '''Display a list of PIL.Image.Image objects in one resizable window, one at a time, with
    Prev/Next buttons (left/right arrow keys also work) and an "i of n" label. The current image
    is scaled (preserving aspect ratio) to fit the window, and rescales live as the window is
    resized. Images are shown from memory only - nothing is read from or written to disk here.

    kwargs:
      window_title - text for the window's title bar (default 'QR code preview')
    '''
    if not images:
        print('g_show_image_gallery(): no images to display.')
        return

    window_title = kwargs.get('window_title', 'QR code preview')
    state = {'index': 0}

    root = tk.Tk()
    root.title(window_title)
    root.geometry('500x550')
    root.minsize(200, 200)

    image_label = tk.Label(root, bg='gray85')
    image_label.pack(fill=tk.BOTH, expand=True)

    counter_label = tk.Label(root, text='')
    counter_label.pack(side=tk.BOTTOM, pady=4)

    nav_frame = tk.Frame(root)
    nav_frame.pack(side=tk.BOTTOM, pady=4)
    prev_button = tk.Button(nav_frame, text='◀ Prev')
    prev_button.pack(side=tk.LEFT, padx=8)
    next_button = tk.Button(nav_frame, text='Next ▶')
    next_button.pack(side=tk.LEFT, padx=8)

    def _render():
        img = images[state['index']]
        avail_w = max(image_label.winfo_width(), 50)
        avail_h = max(image_label.winfo_height(), 50)
        scale = min(avail_w / img.width, avail_h / img.height)
        new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
        resized = img.resize(new_size, Image.LANCZOS)
        photo = ImageTk.PhotoImage(resized)
        image_label.configure(image=photo)
        image_label.image = photo  # keep a reference - tkinter drops it otherwise
        counter_label.configure(text='{} of {}'.format(state['index'] + 1, len(images)))

    def _go_prev(_event=None):
        state['index'] = (state['index'] - 1) % len(images)
        _render()

    def _go_next(_event=None):
        state['index'] = (state['index'] + 1) % len(images)
        _render()

    prev_button.configure(command=_go_prev)
    next_button.configure(command=_go_next)
    root.bind('<Left>', _go_prev)
    root.bind('<Right>', _go_next)
    image_label.bind('<Configure>', lambda _event: _render())

    root.mainloop()
