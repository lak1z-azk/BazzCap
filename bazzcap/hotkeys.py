
import os
import socket
import subprocess
import sys
import threading
import shutil
import time

SOCKET_DIR =os .path .expanduser ("~/.local/share/bazzcap")
SOCKET_PATH =os .path .join (SOCKET_DIR ,"bazzcap.sock")

class HotkeyManager :

    def __init__ (self ):
        self ._listeners ={}
        self ._bindings ={}
        self ._running =False
        self ._pynput_listener =None
        self ._socket_server =None
        self ._socket_thread =None

    def register (self ,name :str ,key_combo :str ,callback ):

        self ._listeners [name ]=callback
        self ._bindings [key_combo .lower ()]=name

    def reregister (self ,new_bindings :dict ):

        self ._bindings .clear ()
        for name ,combo in new_bindings .items ():
            if combo and name in self ._listeners :
                self ._bindings [combo .lower ()]=name

        self ._register_desktop_shortcuts ()

    def start (self ):

        if self ._running :
            return
        self ._running =True

        self ._start_socket_server ()

        self ._register_desktop_shortcuts ()

        try :
            self ._start_pynput ()
        except Exception :
            pass

    def stop (self ):

        self ._running =False

        self ._unregister_desktop_shortcuts ()

        if self ._pynput_listener :
            try :
                self ._pynput_listener .stop ()
            except Exception :
                pass
            self ._pynput_listener =None

        if self ._socket_server :
            try :
                self ._socket_server .close ()
            except Exception :
                pass
            self ._socket_server =None

        try :
            os .unlink (SOCKET_PATH )
        except OSError :
            pass

    def _start_socket_server (self ):

        os .makedirs (SOCKET_DIR ,exist_ok =True )

        try :
            os .unlink (SOCKET_PATH )
        except OSError :
            pass

        self ._socket_server =socket .socket (socket .AF_UNIX ,socket .SOCK_STREAM )
        self ._socket_server .settimeout (1.0 )
        self ._socket_server .bind (SOCKET_PATH )
        os .chmod (SOCKET_PATH ,0o600 )
        self ._socket_server .listen (5 )

        self ._socket_thread =threading .Thread (
        target =self ._socket_listen_loop ,daemon =True
        )
        self ._socket_thread .start ()

    def _socket_listen_loop (self ):

        while self ._running :
            try :
                conn ,_ =self ._socket_server .accept ()
                data =conn .recv (256 ).decode ("utf-8",errors ="ignore").strip ()
                conn .close ()

                cursor_pos =None
                name =data
                if "@"in data :
                    name ,pos_str =data .split ("@",1 )
                    try :
                        cx ,cy =pos_str .split (",")
                        cursor_pos =(int (cx ),int (cy ))
                    except (ValueError ,TypeError ):
                        pass

                if name in self ._listeners :
                    callback =self ._listeners [name ]

                    try :
                        callback (cursor_pos =cursor_pos )
                    except TypeError :
                        callback ()
            except socket .timeout :
                continue
            except (OSError ,ConnectionError ):
                if self ._running :
                    time .sleep (0.5 )
                continue

    def _start_pynput (self ):

        from pynput import keyboard

        hotkeys_dict ={}
        for combo ,name in self ._bindings .items ():
            callback =self ._listeners .get (name )
            if callback :
                pynput_combo =self ._to_pynput_combo (combo )
                if pynput_combo :
                    hotkeys_dict [pynput_combo ]=callback

        if hotkeys_dict :
            self ._pynput_listener =keyboard .GlobalHotKeys (hotkeys_dict )
            self ._pynput_listener .start ()

    @staticmethod
    def _to_pynput_combo (combo :str )->str |None :

        combo =combo .strip ().lower ()

        key_map ={
        "print":"<print_screen>","printscreen":"<print_screen>",
        "print_screen":"<print_screen>","delete":"<delete>",
        "escape":"<esc>","space":"<space>","enter":"<enter>",
        "return":"<enter>","tab":"<tab>","backspace":"<backspace>",
        }

        parts =[]
        remaining =combo

        modifiers_map ={
        "<ctrl>":"<ctrl>","<control>":"<ctrl>",
        "<shift>":"<shift>","<alt>":"<alt>",
        "<super>":"<cmd>","<meta>":"<cmd>",
        }

        for mod_in ,mod_out in modifiers_map .items ():
            if mod_in in remaining :
                parts .append (mod_out )
                remaining =remaining .replace (mod_in ,"")

        remaining =remaining .strip ()

        if remaining in key_map :
            parts .append (key_map [remaining ])
        elif len (remaining )==1 :
            parts .append (remaining )
        elif remaining :
            parts .append (f"<{remaining }>")

        return "+".join (parts )if parts else None

    def _gs_runner (self ):

        in_flatpak =(
        os .path .isfile ("/.flatpak-info")
        or "FLATPAK_ID"in os .environ
        or os .environ .get ("container")=="flatpak"
        or any (p .startswith ("/app/")
        for p in os .environ .get ("PATH","").split (":"))
        )
        if in_flatpak :
            if not shutil .which ("flatpak-spawn"):
                return None
            use_flatpak =True
        elif shutil .which ("gsettings"):
            use_flatpak =False
        else :
            return None

        def gs (*args ):
            if use_flatpak :
                cmd =["flatpak-spawn","--host","gsettings"]+list (args )
            else :
                cmd =["gsettings"]+list (args )
            return subprocess .run (cmd ,capture_output =True ,text =True ,timeout =5 )
        return gs

    def _unregister_desktop_shortcuts (self ):

        desktop =os .environ .get ("XDG_CURRENT_DESKTOP","").lower ()
        if "gnome"in desktop :
            self ._unregister_gnome_shortcuts ()
        elif "kde"in desktop or "plasma"in desktop :
            self ._unregister_kde_shortcuts ()

    def _unregister_gnome_shortcuts (self ):

        gs =self ._gs_runner ()
        if gs is None :
            return

        schema ="org.gnome.settings-daemon.plugins.media-keys"
        key ="custom-keybindings"

        try :
            result =gs ("get",schema ,key )
            existing =result .stdout .strip ()
            if existing =="@as []"or not existing :
                return
            existing_list =[
            p .strip ().strip ("'\"")
            for p in existing .strip ("[]").split (",")
            if p .strip ()
            ]
        except Exception :
            return

        non_bazzcap =[]
        for path in existing_list :
            if "bazzcap"in path :
                binding_schema =f"{schema }.custom-keybinding:{path }"
                try :
                    gs ("reset",binding_schema ,"name")
                    gs ("reset",binding_schema ,"command")
                    gs ("reset",binding_schema ,"binding")
                except Exception :
                    pass
            else :
                non_bazzcap .append (path )

        if non_bazzcap :
            paths_str ="["+", ".join (f"'{p }'"for p in non_bazzcap )+"]"
        else :
            paths_str ="@as []"
        try :
            gs ("set",schema ,key ,paths_str )
        except Exception :
            pass

    def _register_desktop_shortcuts (self ):

        desktop =os .environ .get ("XDG_CURRENT_DESKTOP","").lower ()
        if "gnome"in desktop :
            self ._register_gnome_shortcuts ()
        elif "kde"in desktop or "plasma"in desktop :
            self ._register_kde_shortcuts ()

    def _register_gnome_shortcuts (self ):

        gs =self ._gs_runner ()
        if gs is None :
            return
        schema ="org.gnome.settings-daemon.plugins.media-keys"
        key ="custom-keybindings"
        base_path ="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"

        try :
            result =gs ("get",schema ,key )
            existing =result .stdout .strip ()
            if existing =="@as []"or not existing :
                existing_list =[]
            else :
                existing_list =[
                p .strip ().strip ("'\"")
                for p in existing .strip ("[]").split (",")
                if p .strip ()
                ]
        except Exception :
            existing_list =[]

        bazzcap_existing ={p for p in existing_list if "bazzcap"in p }
        non_bazzcap =[p for p in existing_list if "bazzcap"not in p ]

        display_names ={
        "capture_fullscreen":"BazzCap: Fullscreen",
        "capture_region":"BazzCap: Region",
        "capture_window":"BazzCap: Window",
        }

        new_entries =[]
        for combo ,name in self ._bindings .items ():
            path =f"{base_path }/bazzcap-{name }/"
            binding_schema =f"{schema }.custom-keybinding:{path }"

            display =display_names .get (name ,f"BazzCap: {name }")

            src_trigger =os .path .join (
            os .path .dirname (os .path .abspath (__file__ )),"_trigger.py"
            )
            dst_trigger =os .path .join (SOCKET_DIR ,"_trigger.py")
            try :
                import shutil as _shutil
                _shutil .copy2 (src_trigger ,dst_trigger )
            except OSError :
                pass
            trigger_cmd =f"python3 {dst_trigger } {name }"

            if path in bazzcap_existing :

                try :
                    gs ("set",binding_schema ,"command",trigger_cmd )
                    gnome_combo =self ._to_gnome_combo (combo )
                    gs ("set",binding_schema ,"binding",gnome_combo )
                except (subprocess .SubprocessError ,OSError ):
                    pass
                new_entries .append (path )
                bazzcap_existing .discard (path )
                continue

            gnome_combo =self ._to_gnome_combo (combo )

            try :
                gs ("set",binding_schema ,"name",display )
                gs ("set",binding_schema ,"command",trigger_cmd )
                gs ("set",binding_schema ,"binding",gnome_combo )
                new_entries .append (path )
            except (subprocess .SubprocessError ,OSError ):
                pass

        all_paths =non_bazzcap +new_entries
        if all_paths :
            paths_str ="["+", ".join (f"'{p }'"for p in all_paths )+"]"
            try :
                gs ("set",schema ,key ,paths_str )
            except (subprocess .SubprocessError ,OSError ):
                pass

    @staticmethod
    def _to_gnome_combo (combo :str )->str :

        combo =combo .strip ().lower ()

        key_map ={
        "print":"Print","printscreen":"Print",
        "print_screen":"Print","delete":"Delete",
        "escape":"Escape","space":"space",
        "enter":"Return","return":"Return",
        "tab":"Tab","backspace":"BackSpace",
        }

        parts =[]
        remaining =combo

        for mod in ["<ctrl>","<control>","<shift>","<alt>",
        "<super>","<meta>"]:
            gnome_mod ={
            "<ctrl>":"<Ctrl>","<control>":"<Ctrl>",
            "<shift>":"<Shift>","<alt>":"<Alt>",
            "<super>":"<Super>","<meta>":"<Super>",
            }.get (mod ,"")
            if mod in remaining :
                parts .append (gnome_mod )
                remaining =remaining .replace (mod ,"")

        remaining =remaining .strip ()
        if remaining in key_map :
            parts .append (key_map [remaining ])
        elif len (remaining )==1 :
            parts .append (remaining .lower ())
        elif remaining :
            parts .append (remaining .capitalize ())

        return "".join (parts )

    def _register_kde_shortcuts (self ):

        apps_dir =os .path .expanduser ("~/.local/share/applications")
        os .makedirs (apps_dir ,exist_ok =True )

        src_trigger =os .path .join (
        os .path .dirname (os .path .abspath (__file__ )),"_trigger.py"
        )
        dst_trigger =os .path .join (SOCKET_DIR ,"_trigger.py")
        try :
            import shutil as _shutil
            _shutil .copy2 (src_trigger ,dst_trigger )
        except OSError :
            pass

        display_names ={
        "capture_fullscreen":"BazzCap: Fullscreen",
        "capture_region":"BazzCap: Region",
        "capture_window":"BazzCap: Window",
        }

        for combo ,name in self ._bindings .items ():
            kde_combo =self ._to_kde_combo (combo )
            display =display_names .get (name ,f"BazzCap: {name }")
            trigger_cmd =f"python3 {dst_trigger } {name }"
            desktop_id =f"bazzcap-{name }"
            desktop_path =os .path .join (apps_dir ,f"{desktop_id }.desktop")

            desktop_content =(
            "[Desktop Entry]\n"
            f"Name={display }\n"
            f"Exec={trigger_cmd }\n"
            "Type=Application\n"
            "NoDisplay=true\n"
            "Terminal=false\n"
            f"X-KDE-Shortcuts={kde_combo }\n"
            )
            try :
                with open (desktop_path ,"w")as f :
                    f .write (desktop_content )
                os .chmod (desktop_path ,0o755 )
            except OSError :
                continue

            try :

                qdbus =None
                for tool in ("qdbus6","qdbus"):
                    if shutil .which (tool ):
                        qdbus =tool
                        break

                if qdbus :

                    subprocess .run (
                    [qdbus ,"org.kde.KGlobalAccel",
                    "/kglobalaccel",
                    "org.kde.KGlobalAccel.blockGlobalShortcuts","false"],
                    capture_output =True ,timeout =5 ,
                    )

                kwrite =None
                for tool in ("kwriteconfig6","kwriteconfig5"):
                    if shutil .which (tool ):
                        kwrite =tool
                        break
                if kwrite :
                    shortcut_val =f"{kde_combo },none,{display }"
                    subprocess .run (
                    [kwrite ,"--file","kglobalshortcutsrc",
                    "--group",f"{desktop_id }.desktop",
                    "--key","_launch",shortcut_val ],
                    capture_output =True ,timeout =5 ,
                    )
            except (subprocess .SubprocessError ,OSError ):
                pass

        try :
            subprocess .run (
            ["dbus-send","--type=signal","--dest=org.kde.KGlobalAccel",
            "/kglobalaccel","org.kde.KGlobalAccel.yourShortcutsChanged",
            "array:string:"],
            capture_output =True ,timeout =5 ,
            )
        except (subprocess .SubprocessError ,OSError ):
            pass

    def _unregister_kde_shortcuts (self ):

        apps_dir =os .path .expanduser ("~/.local/share/applications")
        shortcut_names =[
        "capture_fullscreen","capture_region","capture_window",
        ]
        for name in shortcut_names :
            desktop_id =f"bazzcap-{name }"
            desktop_path =os .path .join (apps_dir ,f"{desktop_id }.desktop")
            try :
                os .unlink (desktop_path )
            except OSError :
                pass

            kwrite =None
            for tool in ("kwriteconfig6","kwriteconfig5"):
                if shutil .which (tool ):
                    kwrite =tool
                    break
            if kwrite :
                try :
                    subprocess .run (
                    [kwrite ,"--file","kglobalshortcutsrc",
                    "--group",f"{desktop_id }.desktop",
                    "--key","_launch","--delete"],
                    capture_output =True ,timeout =5 ,
                    )
                except (subprocess .SubprocessError ,OSError ):
                    pass

    @staticmethod
    def _to_kde_combo (combo :str )->str :

        combo =combo .strip ().lower ()
        key_map ={
        "print":"Print","printscreen":"Print",
        "print_screen":"Print","delete":"Delete",
        "escape":"Escape","space":"Space",
        "enter":"Return","return":"Return",
        "tab":"Tab","backspace":"Backspace",
        }

        parts =[]
        remaining =combo
        for mod_in ,mod_out in [
        ("<ctrl>","Ctrl"),("<control>","Ctrl"),
        ("<shift>","Shift"),("<alt>","Alt"),
        ("<super>","Meta"),("<meta>","Meta"),
        ]:
            if mod_in in remaining :
                parts .append (mod_out )
                remaining =remaining .replace (mod_in ,"")

        remaining =remaining .strip ()
        if remaining in key_map :
            parts .append (key_map [remaining ])
        elif len (remaining )==1 :
            parts .append (remaining .upper ())
        elif remaining :
            parts .append (remaining .capitalize ())

        return "+".join (parts )

    def is_available (self )->bool :

        return True
