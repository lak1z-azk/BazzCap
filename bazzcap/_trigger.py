#!/usr/bin/env python3

import os
import re
import socket
import subprocess
import sys

SOCKET_PATH =os .path .expanduser ("~/.local/share/bazzcap/bazzcap.sock")

def main ():
    if len (sys .argv )<2 :
        sys .exit (1 )

    command =sys .argv [1 ]

    x ,y =0 ,0
    try :
        r =subprocess .run (
        ["xdotool","getmouselocation"],
        capture_output =True ,text =True ,timeout =3 ,
        )
        m =re .search (r"x:(\d+) y:(\d+)",r .stdout or "")
        if m :
            x ,y =int (m .group (1 )),int (m .group (2 ))
    except (subprocess .SubprocessError ,OSError ,FileNotFoundError ):
        pass

    try :
        s =socket .socket (socket .AF_UNIX ,socket .SOCK_STREAM )
        s .connect (SOCKET_PATH )
        s .send (f"{command }@{x },{y }".encode ())
        s .close ()
    except (OSError ,ConnectionRefusedError ):
        pass

if __name__ =="__main__":
    main ()
