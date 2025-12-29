#!/bin/bash
# Bash script to engage scanner trunk systems and open browser to monitor
# web page
# This script should be set to auto start at boot.
# location for autoboot should set here /home/pi/.config/autostart create file if not created already
# example of configuration
# [Desktop Entry]
#  Name=Scanner Menu
#  Exec=/usr/bin/x-terminal-emulator -e /home/pi/scanner_apps/scanning_menu.sh

# Change default browser
xdg-settings set default-web-browser chromium.desktop
# xdg-open http://localhost:8080

# Change directory to where the rx.py exec is at.
cd /home/pi/op25/op25/gr-op25_repeater/apps

x-terminal-emulator -e ./multi_rx.py -c /home/pi/scanner_apps/scanner/aurora_fire/aurora_fire.json&&
            sleep 5
            x-terminal-emulator -e chromium --app=http://127.0.0.1:8080 --start-maximized --disable-gpu --disable-component-update \
             --enable-chrome-browser-cloud-management&&

# Clear the screen
clear

PS3='Please enter your choice: '

# Names that will be displayed in the menu. Names need to be double quoted
options=("Aurora Fire" "South and East Metro Fire" "CO State Patrol" "Adams County" "Douglas County" \
         "CO DTRS" "Quit Scanning" "Reboot System" "Shutdown System")

select opt in "${options[@]}"
do
    case $opt in
        "Aurora Fire")
            echo "you chose $opt"

            echo "Starting scan of $opt"
            pkill --full "multi_rx.py"
            pkill --full "chromium"
            x-terminal-emulator -e ./multi_rx.py -c /home/pi/scanner_apps/scanner/aurora_fire/aurora_fire.json&&
            sleep 5
            x-terminal-emulator -e chromium --app=http://127.0.0.1:8080 --start-maximized --disable-gpu --disable-component-update \
             --enable-chrome-browser-cloud-management&&
            sleep 1
            ;;

        "South and East Metro Fire")
            echo "you chose $opt"

            echo "Starting scan of $opt"
            pkill --full "multi_rx.py"
            pkill --full "chromium"
            x-terminal-emulator -e ./multi_rx.py -c /home/pi/scanner_apps/scanner/southmetro_fire/southmetro.json&&
            sleep 5
            x-terminal-emulator -e chromium --app=http://127.0.0.1:8080 --start-maximized --disable-gpu --disable-component-update \
             --enable-chrome-browser-cloud-management&&
            sleep 1
            ;;

        "CO State Patrol")
            echo "you chose $opt"

            echo "Starting scan of $opt"
            pkill --full "multi_rx.py"
            pkill --full "chromium"
            x-terminal-emulator -e ./multi_rx.py -c /home/pi/scanner_apps/scanner/co_state_patrol/co_state_patrol.json&&
            sleep 5
            x-terminal-emulator -e chromium --app=http://127.0.0.1:8080 --start-maximized --disable-gpu --disable-component-update \
             --enable-chrome-browser-cloud-management&&
            sleep 1
            ;;

        "Adams County")
            echo "you chose $opt"

            echo "Starting scan of $opt"
            pkill --full "multi_rx.py"
            pkill --full "chromium"
            x-terminal-emulator -e ./multi_rx.py -c /home/pi/scanner_apps/scanner/adams/adams.json&&
            sleep 5
            x-terminal-emulator -e chromium --app=http://127.0.0.1:8080 --start-maximized --disable-gpu --disable-component-update \
             --enable-chrome-browser-cloud-management&&
            sleep 1
            ;;

        "Douglas County")
            echo "you chose $opt"

            echo "Starting scan of $opt"
            pkill --full "multi_rx.py"
            pkill --full "chromium"
            x-terminal-emulator -e ./multi_rx.py -c /home/pi/scanner_apps/scanner/douglas/douglas.json&&
            sleep 5
            x-terminal-emulator -e chromium --app=http://127.0.0.1:8080 --start-maximized --disable-gpu --disable-component-update \
             --enable-chrome-browser-cloud-management&&
            sleep 1
            ;;

        "CO DTRS")
            echo "you chose $opt"

            echo "Starting scan of $opt"
            pkill --full "multi_rx.py"
            pkill --full "chromium"
            x-terminal-emulator -e ./multi_rx.py -c /home/pi/scanner_apps/scanner/co_dtrs/co_dtrs.json&&
            sleep 5
            x-terminal-emulator -e chromium --app=http://127.0.0.1:8080 --start-maximized --disable-gpu --disable-component-update \
             --enable-chrome-browser-cloud-management&&
            sleep 1
            ;;

        "Quit Scanning")
            pkill --full "multi_rx.py"
            pkill --full "chromium"
            break
            ;;

        "Reboot System")
            echo "Reboot System"
            sudo reboot
            ;;

        "Shutdown System")
            echo "System shutdown"
            sudo shutdown now
            ;;
        *) echo "invalid option $REPLY. Please input correct menu number";;
    esac
done
