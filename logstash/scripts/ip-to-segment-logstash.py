#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2021 Battelle Energy Alliance, LLC.  All rights reserved.

import sys
import os
import re
import argparse
import struct
import ipaddress
import itertools
import json
import pprint
import uuid
from collections import defaultdict

UNSPECIFIED_TAG = '<~<~<none>~>~>'
HOST_LIST_IDX = 0
SEGMENT_LIST_IDX = 1

JSON_MAP_TYPE_SEGMENT = 'segment'
JSON_MAP_TYPE_HOST = 'host'
JSON_MAP_KEY_ADDR = 'address'
JSON_MAP_KEY_NAME = 'name'
JSON_MAP_KEY_TAG = 'tag'
JSON_MAP_KEY_TYPE = 'type'

###################################################################################################
# print to stderr
def eprint(*args, **kwargs):
  print(*args, file=sys.stderr, **kwargs)

###################################################################################################
# main
def main():

  # extract arguments from the command line
  # print (sys.argv[1:]);
  parser = argparse.ArgumentParser(description='Logstash IP address to Segment Filter Creator', add_help=False, usage='ip-to-segment-logstash.py <arguments>')
  parser.add_argument('-m', '--mixed', dest='mixedInput', metavar='<STR>', type=str, nargs='*', default='', help='Input mixed JSON mapping file(s)')
  parser.add_argument('-s', '--segment', dest='segmentInput', metavar='<STR>', type=str, nargs='*', default='', help='Input segment mapping file(s)')
  parser.add_argument('-h', '--host', dest='hostInput', metavar='<STR>', type=str, nargs='*', default='', help='Input host mapping file(s)')
  parser.add_argument('-o', '--output', dest='output', metavar='<STR>', type=str, default='-', help='Output file')
  try:
    parser.error = parser.exit
    args = parser.parse_args()
  except SystemExit:
    parser.print_help()
    exit(2)

  # read each input file into its own list
  segmentLines = []
  hostLines = []
  mixedEntries = []

  for inFile in args.segmentInput:
    if os.path.isfile(inFile):
      segmentLines.extend([line.strip() for line in open(inFile)])

  for inFile in args.hostInput:
    if os.path.isfile(inFile):
      hostLines.extend([line.strip() for line in open(inFile)])

  for inFile in args.mixedInput:
    try:
      tmpMixedEntries = json.load(open(inFile, 'r'))
      if isinstance(tmpMixedEntries, list):
        mixedEntries.extend(tmpMixedEntries);
    except:
      pass

  # remove comments
  segmentLines = list(filter(lambda x: (len(x) > 0) and (not x.startswith('#')), segmentLines))
  hostLines = list(filter(lambda x: (len(x) > 0) and (not x.startswith('#')), hostLines))

  if (len(segmentLines) > 0) or (len(hostLines) > 0) or (len(mixedEntries) > 0):

    filterId = 0
    addedFields = set()

    outFile = open(args.output, 'w+') if (args.output and args.output != '-') else sys.stdout
    try:
      print('filter {', file=outFile)
      print("", file=outFile)
      print("  # this file was automatically generated by {}".format(os.path.basename(__file__)), file=outFile)
      print("", file=outFile)

      # process segment mappings into a dictionary of two dictionaries of lists (one for hosts, one for segments)
      # eg., tagListMap[required tag name][HOST_LIST_IDX|SEGMENT_LIST_IDX][network segment name] = [172.16.0.0/12, 192.168.0.0/24, 10.0.0.41]
      tagListMap = defaultdict(lambda: [defaultdict(list), defaultdict(list)])

      # handle segment mappings
      for line in segmentLines:
        # CIDR to network segment format:
        #   IP(s)|segment name|required tag
        #
        # where:
        #   IP(s): comma-separated list of CIDR-formatted network IP addresses
        #          eg., 10.0.0.0/8, 169.254.0.0/16, 172.16.10.41
        #
        #   segment name: segment name to be assigned when event IP address(es) match
        #
        #   required tag (optional): only check match and apply segment name if the event
        #                            contains this tag
        values = [x.strip() for x in line.split('|')]
        if len(values) >= 2:
          networkList = []
          for ip in ''.join(values[0].split()).split(','):
            try:
              networkList.append(str(ipaddress.ip_network(ip)).lower() if ('/' in ip) else str(ipaddress.ip_address(ip)).lower())
            except ValueError:
              eprint('"{}" is not a valid IP address, ignoring'.format(ip))
          segmentName = values[1]
          tagReq = values[2] if ((len(values) >= 3) and (len(values[2]) > 0)) else UNSPECIFIED_TAG
          if (len(networkList) > 0) and (len(segmentName) > 0):
            tagListMap[tagReq][SEGMENT_LIST_IDX][segmentName].extend(networkList)
          else:
            eprint('"{}" is not formatted correctly, ignoring'.format(line))
        else:
          eprint('"{}" is not formatted correctly, ignoring'.format(line))

      # handle hostname mappings
      macAddrRegex = re.compile(r'([a-fA-F0-9]{2}[:|\-]?){6}')
      for line in hostLines:
        # IP or MAC address to host name map:
        #   address|host name|required tag
        #
        # where:
        #   address: comma-separated list of IPv4, IPv6, or MAC addresses
        #          eg., 172.16.10.41, 02:42:45:dc:a2:96, 2001:0db8:85a3:0000:0000:8a2e:0370:7334
        #
        #   host name: host name to be assigned when event address(es) match
        #
        #   required tag (optional): only check match and apply host name if the event
        #                            contains this tag
        #
        values = [x.strip() for x in line.split('|')]
        if len(values) >= 2:
          addressList = []
          for addr in ''.join(values[0].split()).split(','):
            try:
              # see if it's an IP address
              addressList.append(str(ipaddress.ip_address(addr)).lower())
            except ValueError:
              # see if it's a MAC address
              if re.match(macAddrRegex, addr):
                # prepend _ temporarily to distinguish a mac address
                addressList.append("_{}".format(addr.replace('-', ':').lower()))
              else:
                eprint('"{}" is not a valid IP or MAC address, ignoring'.format(ip))
          hostName = values[1]
          tagReq = values[2] if ((len(values) >= 3) and (len(values[2]) > 0)) else UNSPECIFIED_TAG
          if (len(addressList) > 0) and (len(hostName) > 0):
            tagListMap[tagReq][HOST_LIST_IDX][hostName].extend(addressList)
          else:
            eprint('"{}" is not formatted correctly, ignoring'.format(line))
        else:
          eprint('"{}" is not formatted correctly, ignoring'.format(line))

      # handle mixed entries from the JSON-formatted file
      for entry in mixedEntries:

        # the entry must at least contain type, address, name; may optionally contain tag
        if (isinstance(entry, dict) and
            all(key in entry for key in (JSON_MAP_KEY_TYPE, JSON_MAP_KEY_NAME, JSON_MAP_KEY_ADDR)) and
            entry[JSON_MAP_KEY_TYPE] in (JSON_MAP_TYPE_SEGMENT, JSON_MAP_TYPE_HOST) and
            (len(entry[JSON_MAP_KEY_NAME]) > 0) and
            (len(entry[JSON_MAP_KEY_ADDR]) > 0)):

          addressList = []
          networkList = []

          tagReq = entry[JSON_MAP_KEY_TAG] if (JSON_MAP_KEY_TAG in entry) and (len(entry[JSON_MAP_KEY_TAG]) > 0) else UNSPECIFIED_TAG

          # account for comma-separated multiple addresses per 'address' value
          for addr in ''.join(entry[JSON_MAP_KEY_ADDR].split()).split(','):

            if (entry[JSON_MAP_KEY_TYPE] == JSON_MAP_TYPE_SEGMENT):
              # potentially interpret address as a CIDR-formatted subnet
              try:
                networkList.append(str(ipaddress.ip_network(addr)).lower() if ('/' in addr) else str(ipaddress.ip_address(addr)).lower())
              except ValueError:
                eprint('"{}" is not a valid IP address, ignoring'.format(addr))

            else:
              # should be an IP or MAC address
              try:
                # see if it's an IP address
                addressList.append(str(ipaddress.ip_address(addr)).lower())
              except ValueError:
                # see if it's a MAC address
                if re.match(macAddrRegex, addr):
                  # prepend _ temporarily to distinguish a mac address
                  addressList.append("_{}".format(addr.replace('-', ':').lower()))
                else:
                  eprint('"{}" is not a valid IP or MAC address, ignoring'.format(ip))

          if (len(networkList) > 0):
            tagListMap[tagReq][SEGMENT_LIST_IDX][entry[JSON_MAP_KEY_NAME]].extend(networkList)

          if (len(addressList) > 0):
            tagListMap[tagReq][HOST_LIST_IDX][entry[JSON_MAP_KEY_NAME]].extend(addressList)

      # go through the lists of segments/hosts, which will now be organized by required tag first, then
      # segment/host name, then the list of addresses
      for tag, nameMaps in tagListMap.items():
        print("", file=outFile)

        # if a tag name is specified, print the IF statement verifying the tag's presence
        if tag != UNSPECIFIED_TAG:
          print('  if ("{}" in [tags]) {{'.format(tag), file=outFile)
        try:

          # for the host names(s) to be checked, create two filters, one for source IP|MAC and one for dest IP|MAC
          for hostName, addrList in nameMaps[HOST_LIST_IDX].items():

            # ip addresses mapped to hostname
            ipList = list(set([a for a in addrList if not a.startswith('_')]))
            if (len(ipList) >= 1):
              for source in ['source', 'destination']:
                filterId += 1
                newFieldName = "".join([f"[{x}]" for x in [source, "hostname"]])
                print("", file=outFile)
                print('    if ([{}][ip]) and ({}) {{ '.format(source, ' or '.join(['([{}][ip] == "{}")'.format(source, ip) for ip in ipList])), file=outFile)
                print('      mutate {{ id => "mutate_add_autogen_{}_ip_hostname_{}"'.format(source, filterId), file=outFile)
                print('        add_field => {{ "{}" => "{}" }}'.format(newFieldName, hostName), file=outFile)
                print("      }", file=outFile)
                print("    }", file=outFile)
                addedFields.add(newFieldName)

            # mac addresses mapped to hostname
            macList = list(set([a for a in addrList if a.startswith('_')]))
            if (len(macList) >= 1):
              for source in ['source', 'destination']:
                filterId += 1
                newFieldName = "".join([f"[{x}]" for x in [source, "hostname"]])
                print("", file=outFile)
                print('    if ([{}][mac]) and ({}) {{ '.format(source, ' or '.join(['([{}][mac] == "{}")'.format(source, mac[1:]) for mac in macList])), file=outFile)
                print('      mutate {{ id => "mutate_add_autogen_{}_mac_hostname_{}"'.format(source, filterId), file=outFile)
                print('        add_field => {{ "{}" => "{}" }}'.format(newFieldName, hostName), file=outFile)
                print("      }", file=outFile)
                print("    }", file=outFile)
                addedFields.add(newFieldName)

          # for the segment(s) to be checked, create two cidr filters, one for source IP and one for dest IP
          for segmentName, ipList in nameMaps[SEGMENT_LIST_IDX].items():
            ipList = list(set(ipList))
            for source in ['source', 'destination']:
              filterId += 1
              # ip addresses/ranges mapped to network segment names
              newFieldName = "".join([f"[{x}]" for x in [source, "segment"]])
              print("", file=outFile)
              print("    if ([{}][ip]) {{ cidr {{".format(source), file=outFile)
              print('      id => "cidr_autogen_{}_segment_{}"'.format(source, filterId), file=outFile)
              print('      address => [ "%{{[{}][ip]}}" ]'.format(source), file=outFile)
              print('      network => [ {} ]'.format(', '.join('"{}"'.format(ip) for ip in ipList)), file=outFile)
              print('      add_tag => [ "{}" ]'.format(segmentName), file=outFile)
              print('      add_field => {{ "{}" => "{}" }}'.format(newFieldName, segmentName), file=outFile)
              print("    } }", file=outFile)
              addedFields.add("{}".format(newFieldName))

        finally:
          # if a tag name is specified, close the IF statement verifying the tag's presence
          if tag != UNSPECIFIED_TAG:
            print("", file=outFile)
            print('  }} # end (if "{}" in [tags])'.format(tag), file=outFile)

    finally:
      # deduplicate any added fields
      if addedFields:
        print("", file=outFile)
        print('  # deduplicate any added fields', file=outFile)
        for field in list(itertools.product(['source', 'destination'], ['hostname', 'segment'])):
          newFieldName = newFieldName = "".join([f"[{x}]" for x in [field[0], "field[1]"]])
          if newFieldName in addedFields:
            print("", file=outFile)
            print('  if ({}) {{ '.format(newFieldName), file=outFile)
            print('    ruby {{ id => "ruby{}deduplicate"'.format(''.join(c for c, _ in itertools.groupby(re.sub('[^0-9a-zA-Z]+', '_', newFieldName)))), file=outFile)
            print('      code => "', file=outFile)
            print("        fieldVals = event.get('{}')".format(newFieldName), file=outFile)
            print("        if fieldVals.kind_of?(Array) then event.set('{}', fieldVals.uniq) end".format(newFieldName), file=outFile)
            print('      "', file=outFile)
            print('  } }', file=outFile)

      # close out filter with ending }
      print("", file=outFile)
      print('} # end Filter', file=outFile)

    if outFile is not sys.stdout:
      outFile.close()

if __name__ == '__main__':
  main()