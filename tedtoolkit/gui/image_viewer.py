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
    state = {'index': 0, 'pending_resize': None}
    # Every PhotoImage ever rendered is kept alive here for the window's lifetime (trimmed to the
    # last few). A window fires several <Configure> events in a rapid burst while first being laid
    # out/positioned by the window manager; relying on a single `image_label.image = photo`
    # reference (the usual tkinter idiom) lets Python's refcounting tear down an EARLIER photo's
    # underlying Tcl image in the middle of that burst, which can race with a still-in-flight
    # configure() call and raise "image pyimageN doesn't exist". Never dropping a photo's last
    # reference until well after it could possibly still be in use sidesteps the race entirely -
    # the memory cost is negligible for a gallery of small QR-code images.
    photo_cache = []

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
        state['pending_resize'] = None
        img = images[state['index']]
        avail_w = max(image_label.winfo_width(), 50)
        avail_h = max(image_label.winfo_height(), 50)
        scale = min(avail_w / img.width, avail_h / img.height)
        new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
        resized = img.resize(new_size, Image.LANCZOS)
        photo = ImageTk.PhotoImage(resized)
        photo_cache.append(photo)
        del photo_cache[:-4]
        image_label.configure(image=photo)
        counter_label.configure(text='{} of {}'.format(state['index'] + 1, len(images)))

    def _on_configure(_event=None):
        # Debounced: re-render once layout settles rather than once per intermediate event in
        # that initial burst (also reduces how often the race above could even be triggered).
        if state['pending_resize'] is not None:
            root.after_cancel(state['pending_resize'])
        state['pending_resize'] = root.after(50, _render)

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
    image_label.bind('<Configure>', _on_configure)

    root.mainloop()
