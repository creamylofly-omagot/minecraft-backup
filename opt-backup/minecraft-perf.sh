#!/bin/sh
# Host tuning for the Minecraft server. Runs at boot via minecraft-perf.service.
echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
echo performance > /sys/devices/system/cpu/cpu1/cpufreq/scaling_governor 2>/dev/null
echo 10 > /proc/sys/vm/swappiness

# Paper 26.2 binds RCON to server-ip (now all interfaces) and ignores rcon.bind,
# so restrict RCON and Java to loopback + the home LAN.
iptables  -C INPUT -p tcp --dport 25575 ! -i lo -j DROP 2>/dev/null || iptables  -A INPUT -p tcp --dport 25575 ! -i lo -j DROP
ip6tables -C INPUT -p tcp --dport 25575 ! -i lo -j DROP 2>/dev/null || ip6tables -A INPUT -p tcp --dport 25575 ! -i lo -j DROP
iptables  -C INPUT -p tcp --dport 25565 ! -s 192.168.0.0/16 ! -i lo -j DROP 2>/dev/null || iptables -A INPUT -p tcp --dport 25565 ! -s 192.168.0.0/16 ! -i lo -j DROP
