#!/bin/bash
set -v
sudo /sbin/hdparm -I $1 | grep SECURITY\ ERASE
sudo /sbin/hdparm --user-master u --security-set-pass GEHEIM $1
time sudo /sbin/hdparm --user-master u --security-erase GEHEIM $1
