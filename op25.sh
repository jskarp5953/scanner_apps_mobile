#! /bin/sh

cd ~/op25/op25/gr-op25_repeater/apps

today=`date '+%F_%I:%M:%S-%p'`;

#Audio Server mode
#./audio.py &
#./rx.py -w -W 127.0.0.1 -u 23456 --args 'rtl' -N 'LNA:80' -S 2400000 -f 853.875e6 -o 25000  -T home.csv -q 0 -V -2  2> "$today"__log.2

#Non audio server mode
./rx.py -U --args 'rtl' -N 'LNA:80' -S 2400000 -f 853.875e6 -o 25000  -d -100 -T home.tsv -q 0 -V -2  2> "$today"__log.2
