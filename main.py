import traceback
import tkinter as tk
from tkinter import messagebox

from ui.main_window import PassportPhotoStudio, SplashScreen

if __name__ == "__main__":
    try:
        app = PassportPhotoStudio()
        app.withdraw()

        splash = SplashScreen(app)
        # Center the splash on the primary display.
        splash.update_idletasks()
        sw, sh = splash.winfo_screenwidth(), splash.winfo_screenheight()
        ww, wh = 560, 330
        splash.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
        splash.lift()
        splash.focus_force()

        def finish_startup():
            splash.destroy()
            app.deiconify()
            app.lift()
            app.focus_force()

        splash.animate(finish_startup)
        app.mainloop()
    except tk.TclError as exc:
        traceback.print_exc()
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Passport Photo Studio Pro",
                "The Windows desktop UI could not start.\n\n"
                f"{exc}\n\n"
                "Please make sure the required packages are installed."
            )
            root.destroy()
        except Exception:
            pass
        raise
