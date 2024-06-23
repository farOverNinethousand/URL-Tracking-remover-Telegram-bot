#!/bin/bash

# Dieses Script ist zur Verwendung in Crontab gedacht -> Crontab Eintrag:
# */1 * * * * sh /root/URL-Tracking-remover-Telegram-bot/start.sh

filepath=~/URL-Tracking-remover-Telegram-bot/process.pid

start_script() {
  cd ~/URL-Tracking-remover-Telegram-bot && python3 URLCleanerBot.py > /tmp/urlcleanerbot.log 2>&1 & echo $! >$filepath
}



# Start if pid file does not exist
[ ! -f $filepath ] && start_script && echo URLCleanerBot gestartet weil PID File nicht existiert

thispid=$(cat $filepath)
echo pid ist $thispid

# Partially stolen from: https://stackoverflow.com/questions/3043978/how-to-check-if-a-process-id-pid-exists
# Start if pid does not exist
[ ! -d /proc/$thispid ] && start_script && echo URLCleanerBot gestartet weil PID nicht existiert
# echo Script execution done