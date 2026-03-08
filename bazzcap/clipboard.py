
import subprocess
import shutil
import os
import sys

IS_MACOS = sys.platform == "darwin"

def _is_wayland ():
    return os .environ .get ("WAYLAND_DISPLAY")or os .environ .get ("XDG_SESSION_TYPE")=="wayland"

def _has (cmd ):
    return shutil .which (cmd )is not None

def _qt_copy_image (image_path :str )->bool :
    try :
        from PyQt6 .QtWidgets import QApplication
        from PyQt6 .QtGui import QPixmap ,QImage

        app =QApplication .instance ()
        if app is None :
            return False

        pixmap =QPixmap (image_path )
        if pixmap .isNull ():
            return False

        clipboard =app .clipboard ()
        clipboard .setPixmap (pixmap )
        return True
    except Exception :
        return False

def _qt_copy_text (text :str )->bool :
    try :
        from PyQt6 .QtWidgets import QApplication

        app =QApplication .instance ()
        if app is None :
            return False

        clipboard =app .clipboard ()
        clipboard .setText (text )
        return True
    except Exception :
        return False

def copy_image_to_clipboard (image_path :str )->bool :
    if not os .path .isfile (image_path ):
        return False

    if IS_MACOS:
        # Use osascript to set clipboard to image file
        try:
            script = (
                'set the clipboard to '
                '(read (POSIX file "' + image_path + '") as «class PNGf»)'
            )
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, timeout=5, check=True,
            )
            return True
        except (subprocess.SubprocessError, OSError):
            pass
        return _qt_copy_image(image_path)

    mime ="image/png"
    if image_path .lower ().endswith (".jpg")or image_path .lower ().endswith (".jpeg"):
        mime ="image/jpeg"

    if _is_wayland ()and _has ("wl-copy"):
        try :
            with open (image_path ,"rb")as f :
                subprocess .run (
                ["wl-copy","--type",mime ],
                stdin =f ,timeout =5 ,check =True ,
                )
            return True
        except (subprocess .SubprocessError ,IOError ):
            pass

    if _has ("xclip"):
        try :
            with open (image_path ,"rb")as f :
                subprocess .run (
                ["xclip","-selection","clipboard","-t",mime ,"-i"],
                stdin =f ,timeout =5 ,check =True ,
                )
            return True
        except (subprocess .SubprocessError ,IOError ):
            pass

    if _qt_copy_image (image_path ):
        return True

    if _has ("xsel"):
        try :
            subprocess .run (
            ["xsel","--clipboard","--input"],
            input =image_path .encode (),timeout =5 ,check =True ,
            )
            return True
        except (subprocess .SubprocessError ,IOError ):
            pass

    return False

def copy_text_to_clipboard (text :str )->bool :
    if IS_MACOS:
        try:
            subprocess.run(
                ["pbcopy"],
                input=text.encode(), timeout=5, check=True,
            )
            return True
        except (subprocess.SubprocessError, OSError):
            pass
        return _qt_copy_text(text)

    if _is_wayland ()and _has ("wl-copy"):
        try :
            subprocess .run (
            ["wl-copy",text ],timeout =5 ,check =True ,
            )
            return True
        except subprocess .SubprocessError :
            pass

    if _has ("xclip"):
        try :
            subprocess .run (
            ["xclip","-selection","clipboard"],
            input =text .encode (),timeout =5 ,check =True ,
            )
            return True
        except subprocess .SubprocessError :
            pass

    if _qt_copy_text (text ):
        return True

    return False
