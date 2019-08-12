#!/bin/bash
wget https://baba.das-it-gesicht.de/ -O /tmp/baba.deb
dpkg -i /tmp/baba.deb
apt-get install -f
