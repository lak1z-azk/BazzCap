
import subprocess
import shutil
import os
import tempfile
import time
from enum import Enum ,auto
from pathlib import Path

class CaptureMode (Enum ):
    FULLSCREEN =auto ()
    REGION =auto ()
    WINDOW =auto ()

def _has (cmd ):
    return shutil .which (cmd )is not None

def _run (cmd ,timeout =30 ):
    try :
        r =subprocess .run (
        cmd ,capture_output =True ,text =True ,timeout =timeout ,
        )
        return r .returncode ==0 ,r .stdout .strip ()
    except (FileNotFoundError ,subprocess .TimeoutExpired ,OSError ):
        return False ,""

def _portal_screenshot (interactive :bool =True )->str |None :
    helper =os .path .join (os .path .dirname (__file__ ),"_portal_helper.py")
    if os .path .exists (helper ):
        try :
            r =subprocess .run (
            ["python3",helper ,"screenshot",
            "--interactive"if interactive else "--fullscreen"],
            capture_output =True ,text =True ,timeout =30 ,
            )
            if r .returncode ==0 and r .stdout .strip ():
                path =r .stdout .strip ()
                if os .path .isfile (path ):
                    return path
        except (subprocess .SubprocessError ,OSError ):
            pass

    try :
        token =f"bazzcap_{int (time .time ())}"
        interactive_str ="true"if interactive else "false"
        r =subprocess .run (
        [
        "gdbus","call","--session",
        "--dest","org.freedesktop.portal.Desktop",
        "--object-path","/org/freedesktop/portal/desktop",
        "--method","org.freedesktop.portal.Screenshot.Screenshot",
        "",f"{{'interactive': <{interactive_str }>, 'handle_token': <'{token }'>}}"
        ],
        capture_output =True ,text =True ,timeout =30 ,
        )
    except (subprocess .SubprocessError ,OSError ):
        pass

    return None

def capture_fullscreen (output_path :str )->bool :
    portal_path =_portal_screenshot (interactive =False )
    if portal_path :
        try :
            shutil .copy2 (portal_path ,output_path )
            return True
        except IOError :
            pass

    if _has ("spectacle"):
        ok ,_ =_run (["spectacle","-b","-n","-f","-o",output_path ])
        if ok and os .path .isfile (output_path ):
            return True

    if _has ("gnome-screenshot"):
        ok ,_ =_run (["gnome-screenshot","-f",output_path ])
        if ok and os .path .isfile (output_path ):
            return True

    if _has ("grim"):
        ok ,_ =_run (["grim",output_path ])
        if ok and os .path .isfile (output_path ):
            return True

    if _has ("scrot"):
        ok ,_ =_run (["scrot",output_path ])
        if ok and os .path .isfile (output_path ):
            return True

    if _has ("maim"):
        ok ,_ =_run (["maim",output_path ])
        if ok and os .path .isfile (output_path ):
            return True

    if _has ("import"):
        ok ,_ =_run (["import","-window","root",output_path ])
        if ok and os .path .isfile (output_path ):
            return True

    return False

def capture_region (output_path :str )->bool :
    portal_path =_portal_screenshot (interactive =True )
    if portal_path :
        try :
            shutil .copy2 (portal_path ,output_path )
            return True
        except IOError :
            pass

    if _has ("spectacle"):
        ok ,_ =_run (["spectacle","-b","-n","-r","-o",output_path ])
        if ok and os .path .isfile (output_path ):
            return True

    if _has ("gnome-screenshot"):
        ok ,_ =_run (["gnome-screenshot","-a","-f",output_path ])
        if ok and os .path .isfile (output_path ):
            return True

    if _has ("grim")and _has ("slurp"):
        try :
            slurp =subprocess .run (
            ["slurp"],capture_output =True ,text =True ,timeout =30 ,
            )
            if slurp .returncode ==0 and slurp .stdout .strip ():
                geometry =slurp .stdout .strip ()
                ok ,_ =_run (["grim","-g",geometry ,output_path ])
                if ok and os .path .isfile (output_path ):
                    return True
        except (subprocess .SubprocessError ,OSError ):
            pass

    if _has ("scrot"):
        ok ,_ =_run (["scrot","-s",output_path ])
        if ok and os .path .isfile (output_path ):
            return True

    if _has ("maim")and _has ("slop"):
        try :
            slop =subprocess .run (
            ["slop","-f","%g"],capture_output =True ,text =True ,timeout =30 ,
            )
            if slop .returncode ==0 and slop .stdout .strip ():
                geometry =slop .stdout .strip ()
                ok ,_ =_run (["maim","-g",geometry ,output_path ])
                if ok and os .path .isfile (output_path ):
                    return True
        except (subprocess .SubprocessError ,OSError ):
            pass

    return False

def capture_window (output_path :str )->bool :
    portal_path =_portal_screenshot (interactive =True )
    if portal_path :
        try :
            shutil .copy2 (portal_path ,output_path )
            return True
        except IOError :
            pass

    if _has ("spectacle"):
        ok ,_ =_run (["spectacle","-b","-n","-a","-o",output_path ])
        if ok and os .path .isfile (output_path ):
            return True

    if _has ("gnome-screenshot"):
        ok ,_ =_run (["gnome-screenshot","-w","-f",output_path ])
        if ok and os .path .isfile (output_path ):
            return True

    if _has ("scrot"):
        ok ,_ =_run (["scrot","-u",output_path ])
        if ok and os .path .isfile (output_path ):
            return True

    if _has ("maim")and _has ("xdotool"):
        try :
            xdo =subprocess .run (
            ["xdotool","getactivewindow"],
            capture_output =True ,text =True ,timeout =5 ,
            )
            if xdo .returncode ==0 :
                wid =xdo .stdout .strip ()
                ok ,_ =_run (["maim","-i",wid ,output_path ])
                if ok and os .path .isfile (output_path ):
                    return True
        except (subprocess .SubprocessError ,OSError ):
            pass

    return False

def capture (mode :CaptureMode ,output_path :str )->bool :
    if mode ==CaptureMode .FULLSCREEN :
        return capture_fullscreen (output_path )
    elif mode ==CaptureMode .REGION :
        return capture_region (output_path )
    elif mode ==CaptureMode .WINDOW :
        return capture_window (output_path )
    return False

def detect_available_backends ()->list [str ]:
    backends =[]
    if _has ("gdbus"):
        backends .append ("XDG Portal (gdbus)")
    if _has ("spectacle"):
        backends .append ("Spectacle (KDE)")
    if _has ("gnome-screenshot"):
        backends .append ("GNOME Screenshot")
    if _has ("grim"):
        backends .append ("grim"+(" + slurp"if _has ("slurp")else ""))
    if _has ("scrot"):
        backends .append ("scrot")
    if _has ("maim"):
        backends .append ("maim"+(" + slop"if _has ("slop")else ""))
    if _has ("import"):
        backends .append ("ImageMagick import")
    return backends
