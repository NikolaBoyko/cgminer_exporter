#!/usr/bin/env python3.8

# Copyright 2013 Setkeh Mkfr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 3 of the License, or (at your option) any later
# version.  See COPYING for more details.

# Short Python Example for connecting to The Cgminer API
# Written By: setkeh <https://github.com/setkeh>
# Thanks to Jezzz for all his Support.
# NOTE: When adding a param with a pipe | in bash or ZSH you must wrap the arg in quotes
# E.G "pga|0"

import socket
import os
import json
import pprint
import datetime
from abc import ABC
import tornado
import tornado.ioloop
import tornado.httpserver
import tornado.web
import tornado.options

pp = pprint.PrettyPrinter(indent=4)

status_data = {}

if os.environ.get('THREADS'):
    threads = int(os.environ['THREADS'])
else:
    threads = 0


def line_split(socket_obj):
    buffer = socket_obj.recv(4096)
    done = False
    while not done:
        more = socket_obj.recv(4096)
        if not more:
            done = True
        else:
            buffer = buffer + more
    if buffer:
        return buffer


def get_from_ip(ip):
    data = {}
    for func in ['stats', 'version', 'pools', 'summary', 'devs']:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect((ip, int(4028)))
        data[func] = get_function(s, func)
        s.close()
    return data


def get_function(s, function):
    s.send(str.encode(json.dumps({"command": function})))
    response = line_split(s)
    response = response.decode()
    response = response.replace('\x00', '')
    return json.loads(response)


class HelpHandler(tornado.web.RequestHandler, ABC):
    def get(self):
        self.write("Use /metrics with ?target=IP\n")


class MetricsHandler(tornado.web.RequestHandler, ABC):
    def get(self):
        target = self.get_argument("target", None, True)
        metric_data = get_from_ip(target)
        if 'CGMiner' in metric_data['version']['VERSION'][0]:
            tags = 'instance="%s",cgminer_version="%s",api_version="%s",type="%s",miner="%s"' % (
                target, metric_data['version']['VERSION'][0]['CGMiner'], metric_data['version']['VERSION'][0]['API'],
                metric_data['version']['VERSION'][0]['Type'], metric_data['version']['VERSION'][0]['Miner'])
        elif 'BMMiner' in metric_data['version']['VERSION'][0]:
            tags = 'instance="%s",bmminer_version="%s",api_version="%s",type="%s",miner="%s"' % (
                target, metric_data['version']['VERSION'][0]['BMMiner'], metric_data['version']['VERSION'][0]['API'],
                metric_data['version']['VERSION'][0]['Type'], metric_data['version']['VERSION'][0]['Miner'])
        else:
            tags = 'instance="%s",api_version="%s",type="%s",miner="%s"' % (
                target, metric_data['version']['VERSION'][0]['API'], metric_data['version']['VERSION'][0]['Type'],
                metric_data['version']['VERSION'][0]['Miner'])
        self.write("#CGMiner metrics export\n")
        for metric_type in metric_data:
            if metric_type == "pools":
                self.write(metric_pool(metric_data[metric_type], tags))
            elif metric_type == "summary":
                self.write(metric_summary(metric_data[metric_type], tags))
            elif metric_type == "stats":
                self.write(metric_stats(metric_data[metric_type], tags))


def metric_pool(data, tags):
    string = "# Pools Data\n"
    string += "cgminer_pool_count{%s} %s\n" % (tags, len(data['POOLS']))
    for pool in data['POOLS']:
        local_tags = 'pool="%s",url="%s",stratum_url="%s",%s' % (pool['POOL'], pool['URL'], pool['Stratum URL'], tags)
        string += 'cgminer_pool_diff_accepted{%s} %s\n' % (local_tags, pool['Difficulty Accepted'])
        string += 'cgminer_pool_rejected{%s} %s\n' % (local_tags, pool['Difficulty Accepted'])
        string += 'cgminer_pool_diff_rejected{%s} %s\n' % (local_tags, pool['Difficulty Rejected'])
        string += 'cgminer_pool_stale{%s} %s\n' % (local_tags, pool['Stale'])
        try:
            [hr, mn, ss] = [int(x) for x in pool['Last Share Time'].split(':')]
            share_time = datetime.timedelta(hours=hr, minutes=mn, seconds=ss).seconds
        except Exception:
            share_time = 0
        string += 'cgminer_pool_last_share{%s} %s\n' % (local_tags, share_time)
        string += 'cgminer_pool_getworks{%s} %s\n' % (local_tags, pool['Getworks'])
        string += 'cgminer_pool_last_diff{%s} %s\n' % (local_tags, pool['Last Share Difficulty'])
        if pool['Status'] == "Alive":
            status = 1
        else:
            status = 0
        string += 'cgminer_pool_status{%s} %s\n' % (local_tags, status)
        if pool['Stratum Active']:
            active = 1
        else:
            active = 0
        string += 'cgminer_pool_stratum_active{%s} %s\n' % (local_tags, active)
    return string


def metric_summary(data, tags):
    string = "#Pool Summary\n"
    local_tags = tags
    string += 'cgminer_summary_rejected{%s} %s\n' % (local_tags, data['SUMMARY'][0]['Rejected'])
    string += 'cgminer_summary_found_blocks{%s} %s\n' % (local_tags, data['SUMMARY'][0]['Found Blocks'])
    string += 'cgminer_summary_elapsed{%s} %s\n' % (local_tags, data['SUMMARY'][0]['Elapsed'])
    string += 'cgminer_summary_hardware_errors{%s} %s\n' % (local_tags, data['SUMMARY'][0]['Hardware Errors'])
    string += 'cgminer_summary_total_mh{%s} %s\n' % (local_tags, data['SUMMARY'][0]['Total MH'])
    string += 'cgminer_summary_ghs_average{%s} %s\n' % (local_tags, data['SUMMARY'][0]['GHS av'])
    string += 'cgminer_summary_ghs_5s{%s} %s\n' % (local_tags, data['SUMMARY'][0]['GHS 5s'])

    return string


def metric_stats(data, tags):
    string = "# Stats\n"
    stat_data = data['STATS'][1]
    local_tags = '%s' % tags
    for entry in stat_data:
        if 'temp' in entry:
            temp_num = entry.replace("temp", "")
            value = stat_data[entry]
            if isinstance(value, str):
                value_list = value.split('-')
                value_list = [int(i) for i in value_list]
                value = max(value_list)
            string += 'cgminer_stats_temp{temp="%s",%s} %s\n' % (temp_num, local_tags, value)
        if 'chain_hw' in entry:
            chain_num = entry.replace("chain_hw", "")
            if stat_data['chain_rate%s' % chain_num]:
                string += 'cgminer_stats_chain_rate{chain="%s",%s} %s\n' % (
                    chain_num, local_tags, stat_data['chain_rate%s' % chain_num])
            else:
                string += 'cgminer_stats_chain_rate{chain="%s",%s} %s\n' % (chain_num, local_tags, 0)
            string += 'cgminer_stats_chain_acn{chain="%s",%s} %s\n' % (
                chain_num, local_tags, stat_data['chain_acn%s' % chain_num])
            string += 'cgminer_stats_chain_hw{chain="%s",%s} %s\n' % (
                chain_num, local_tags, stat_data['chain_hw%s' % chain_num])
        if 'fan' in entry:
            fan_num = entry.replace("fan", "")
            string += 'cgminer_stats_fan{fan="%s",%s} %s\n' % (fan_num, local_tags, stat_data['fan%s' % fan_num])
        if 'freq_avg' in entry:
            freq_num = entry.replace("freq_avg", "")
            string += 'cgminer_stats_freq{freq="%s",%s} %s\n' % (freq_num, local_tags,
                                                                 stat_data['freq_avg%s' % freq_num])

    string += 'cgminer_stats_frequency{%s} %s\n' % (local_tags, stat_data['frequency'])

    return string


def main():
    tornado.options.parse_command_line()
    application = tornado.web.Application([
        (r"/", HelpHandler),
        (r"/metrics", MetricsHandler)

    ])
    http_server = tornado.httpserver.HTTPServer(application, idle_connection_timeout=2)
    http_server.bind(9154)
    http_server.start(threads)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
