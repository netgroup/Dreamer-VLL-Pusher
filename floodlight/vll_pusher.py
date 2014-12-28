#!/usr/bin/python

##############################################################################################
# Copyright (C) 2014 Pier Luigi Ventre - (Consortium GARR and University of Rome "Tor Vergata")
# Copyright (C) 2014 Giuseppe Siracusano, Stefano Salsano - (CNIT and University of Rome "Tor Vergata")
# www.garr.it - www.uniroma2.it/netgroup - www.cnit.it
#
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Virtual Leased Line Pusher.
#
# @author Pier Luigi Ventre <pl.ventre@gmail.com>
# @author Giuseppe Siracusano <a_siracusano@tin.it>
# @author Stefano Salsano <stefano.salsano@uniroma2.it>
#
#

import os
import sys
import subprocess
import json
import argparse
import io
import time
import re
import siphash

# XXX Be Careful, For Now The Vll_Pusher Depends On vll_pusher.cfg; This file should be created by the [x] Deployer
# (x = Mininet Deployer, TestBeds Deployer)

# Parse vll options.  Currently supports add and delete actions.
# Syntax:
#   vll_pusher --controller {IP:REST_PORT} --add 
#   vll_pusher --controller {IP:REST_PORT} --delete
def parse_cmd_line():
	parser = argparse.ArgumentParser(description='Virtual Leased Line Pusher')
	parser.add_argument('--controller', dest='controllerRestIp', action='store', default='localhost:8080', help='controller IP:RESTport, e.g., localhost:8080 or A.B.C.D:8080')
	parser.add_argument('--add', dest='action', action='store_const', const='add', default='add', help='action: add')
	parser.add_argument('--delete', dest='action', action='store_const', const='delete', default='add', help='action: delete')
	args = parser.parse_args()	
	if len(sys.argv)==1:
    		parser.print_help()
    		sys.exit(1)	
	return args

# Read From vll_pusher.cfg The Configuration For The Vlls
def read_conf_file():
	global pusher_cfg

	print "*** Read Configuration File For Vll Pusher"
	path = "vll_pusher.cfg"
	if os.path.exists(path):
		conf = open(path,'r')
		pusher_cfg = json.load(conf)
		conf.close()
	else:
		print "No Configuration File Find In %s" % path
		sys.exit(-2)	

	print "*** PUSHER_CFG", json.dumps(pusher_cfg, sort_keys=True, indent=4)

# Utility function for the vlls persisentce
def store_vll(name, dpid):
	# Store created vll attributes in local ./vlls.json
	datetime = time.asctime()
	vllParams = {'name': name, 'Dpid':dpid, 'datetime':datetime}
	str = json.dumps(vllParams)
	vllsDb = open('./vlls.json','a+')
	vllsDb.write(str+"\n")
	vllsDb.close()

intf_to_port_number = {}

def convert_intf_to_port_number(controllerRestIP):

	global intf_to_port_number

	command = "curl -s http://%s/wm/core/controller/switches/json | python -mjson.tool" % (controllerRestIP)
	result = os.popen(command).read()
	parsedResult = json.loads(result)
	default = None	

	for vll in pusher_cfg['vlls']:
		lhs_intf = vll['lhs_intf']
		lhs_dpid = vll['lhs_dpid']
		port_number = intf_to_port_number.get("%s-%s" % (lhs_dpid, lhs_intf), default)
		if port_number == None :
			for switch in parsedResult:
				if switch["dpid"] == lhs_dpid:
					for port in switch["ports"]:
						if port["name"] == lhs_intf:
							port_number = str(port["portNumber"])
							intf_to_port_number["%s-%s" % (lhs_dpid, lhs_intf)] = port_number
		vll['lhs_intf'] = port_number

		rhs_intf = vll['rhs_intf']
		rhs_dpid = vll['rhs_dpid']
		port_number = intf_to_port_number.get("%s-%s" % (rhs_dpid, rhs_intf), default)
		if port_number == None :
			for switch in parsedResult:
				if switch["dpid"] == rhs_dpid:
					for port in switch["ports"]:
						if port["name"] == rhs_intf:
							port_number = str(port["portNumber"])
							intf_to_port_number["%s-%s" % (rhs_dpid, rhs_intf)] = port_number
		vll['rhs_intf'] = port_number

	print "*** PUSHER_CFG", json.dumps(pusher_cfg, sort_keys=True, indent=4)
	print "*** INTFS", json.dumps(intf_to_port_number, sort_keys=True, indent=4)

# Add Vlls Reading All the Information From Configuration File
def add_command(args):
	print "*** Add Vlls From Configuration File"

	print "*** Read Previous Vlls Inserted"
	if os.path.exists('./vlls.json'):
			vllsDb = open('./vlls.json','r')
			vlllines = vllsDb.readlines()
			vllsDb.close()
	else:
			vlllines={}
	
	read_conf_file()

	# We use this algorithm for the name generation	
	key = '0123456789ABCDEF'
	sip = siphash.SipHash_2_4(key)
	# Extract from cmd line options the controlller information
	controllerRestIp = args.controllerRestIp
	# Dictionary that stores the mapping port:next_label
	# We allocate the label using a counter, and we associate for each port used in this execution the next usable label
	# Probably in future we can add the persistence for the label
	sw_port_tag = {}
	convert_intf_to_port_number(controllerRestIp)
	
	# We can have more than one vlls
	for vll in pusher_cfg['vlls']:

		# Retrieve the information
		srcSwitch = vll['lhs_dpid']
		srcPort = vll['lhs_intf']
		dstSwitch = vll['rhs_dpid']
		dstPort = vll['rhs_intf']
		srcLabel = vll['lhs_label']
		dstLabel = vll['rhs_label']

		print "*** Generate Name From VLL (%s-%s-%s) - (%s-%s-%s)" % (srcSwitch, srcPort, srcLabel, dstSwitch, dstPort, dstLabel)
		sip.update(srcSwitch + "$" + srcPort + "$" + dstSwitch + "$" + dstPort + "$" + srcLabel + "$" + dstLabel)
		# Generate the name        
		digest = sip.hash()
		digest = str(digest)


		print "*** Vll Name", digest        
			
		vllExists = False

		# if the vll exists in the vllDb, we don't insert the flow
		for line in vlllines:
			data = json.loads(line)
			if data['name']==(digest):
				print "Vll %s exists already Skip" % digest
				vllExists = True
				break

		if vllExists == True:
			continue

		print "*** Create Vll:"
		print "*** From Source Device OSHI-PE %s Port %s" % (srcSwitch,srcPort)
		print "*** To Destination Device OSHI-PE %s Port %s"% (dstSwitch,dstPort)

		# Retrieving route from source to destination
		# using Routing rest API

		command = "curl -s http://%s/wm/topology/route/%s/%s/%s/%s/json | python -mjson.tool" % (controllerRestIp, srcSwitch, srcPort, dstSwitch, dstPort)
		result = os.popen(command).read()
		parsedResult = json.loads(result)

		print
		#print "*** Sent Command:", command + "\n"
		print "*** Received Result:", result + "\n"

		# Dictionary used for store the label of current vll
		temp_sw_port_tag = {}

		# We insert the rule each two json item, because floodlight's getRoute for each dpid, provides
		# A couple of item the in/out port and the out/in port for the rules forward/reverse - see the
		# output of the previous command 
		temp_key1 = None
		temp_key2 = None
		temp_tag1 = None
		temp_tag2 = None
		ap1Dpid = None
		ap1Port = None
		ap2Dpid = None
		ap2Port = None

		default = 2
		max_value = 4095

		if int(srcLabel) > max_value or int(dstLabel) > max_value:
			print "Ingress or Egress Label Not Allowable"
			sys.exit(-2)
		
		# We generate the labels associated for each port, while the ingress/egress and egress/ingress labels
		# come from the configuration file, because they depend on the local network choice
		for j in range(0, (len(parsedResult))):
			# Label for the LHS port
			if j == 0:
				temp_key1 = srcSwitch + "-" + srcPort
				temp_sw_port_tag[temp_key1] = int(srcLabel)
				if sw_port_tag.get(temp_key1,default) <= int(srcLabel):
					sw_port_tag[temp_key1] = int(srcLabel)
			# Label for the RHS port			
			elif j == (len(parsedResult)-1):
				temp_key1 = dstSwitch + "-" + dstPort
				temp_sw_port_tag[temp_key1] = int(dstLabel)
				if sw_port_tag.get(temp_key1,default) <= int(dstLabel):
					sw_port_tag[temp_key1] = int(dstLabel)			
			# Middle ports			
			else :
				apDPID = parsedResult[j]['switch']
				apPORT = parsedResult[j]['port']
				temp_key1 = apDPID + "-" + str(apPORT)
				value = sw_port_tag.get(temp_key1, default)
				temp_sw_port_tag[temp_key1] = value
				value = value + 1
				sw_port_tag[temp_key1] = value			

		
		
		
		print "*** Current Route Tag:"
		print json.dumps(temp_sw_port_tag, sort_keys=True, indent=4)
		print
		print "*** Global Routes Tag:"
		print json.dumps(sw_port_tag, sort_keys=True, indent=4)
		print 			
		

		# Manage the special case of one hop
		if len(parsedResult) == 2:
			print "*** One Hop Route"
			# The Switch, where we insert the rule
			ap1Dpid = parsedResult[0]['switch']
			# In port
			ap1Port = str(parsedResult[0]['port'])
			temp_key1 = ap1Dpid + "-" + ap1Port
			tag1 = temp_sw_port_tag[temp_key1]
			# ap1Dpid == ap2Dpid			
			ap2Dpid = parsedResult[1]['switch']
			# Out port
			ap2Port = str(parsedResult[1]['port'])
			temp_key2 = ap2Dpid + "-" + ap2Port
			tag2 = temp_sw_port_tag[temp_key2]

			if tag1 == 0 and tag2 ==0:
				# Forward's Rule
				command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".f", ap1Port, ap2Port, controllerRestIp)
				result = os.popen(command).read()
				print "*** Sent Command:", command + "\n"
				print "*** Received Result:", result + "\n"
			elif tag1 !=0 and tag2==0:
				# Forward's Rule
				command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"vlan-id\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"strip-vlan,output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".f", tag1, ap1Port, ap2Port, controllerRestIp)
				result = os.popen(command).read()
				print "*** Sent Command:", command + "\n"
				print "*** Received Result:", result + "\n"
			elif tag1 ==0 and tag2 !=0:
				# Forward's Rule
				command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"vlan-id\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"set-vlan-id=%s,output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".f", "0xffff", ap1Port, tag2, ap2Port, controllerRestIp)
				result = os.popen(command).read()
				print "*** Sent Command:", command + "\n"
				print "*** Received Result:", result + "\n"
			else:
				# Forward's Rule
				command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"vlan-id\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"set-vlan-id=%s,output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".f", tag1, ap1Port, tag2, ap2Port, controllerRestIp)
				result = os.popen(command).read()
				print "*** Sent Command:", command + "\n"
				print "*** Received Result:", result + "\n"

			if tag2 == 0 and tag1 ==0:
				# Reverse Forward's Rule
				command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".r", ap2Port, ap1Port, controllerRestIp)
				result = os.popen(command).read()
				print "*** Sent Command:", command + "\n"
				print "*** Received Result:", result + "\n"				

			elif tag2 != 0 and tag1 ==0:
				# Reverse Forward's Rule
				command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"vlan-id\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"strip-vlan,output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".r", tag2, ap2Port, ap1Port, controllerRestIp)
				result = os.popen(command).read()
				print "*** Sent Command:", command + "\n"
				print "*** Received Result:", result + "\n"
			elif tag2 == 0 and tag1 !=0:
				# Reverse Forward's Rule
				command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"vlan-id\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"set-vlan-id=%s,output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".r", "0xffff", ap2Port, tag1, ap1Port, controllerRestIp)
				result = os.popen(command).read()
				print "*** Sent Command:", command + "\n"
				print "*** Received Result:", result + "\n"
			else:
				# Reverse Forward's Rule
				command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"vlan-id\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"set-vlan-id=%s,output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".r", tag2, ap2Port, tag1, ap1Port, controllerRestIp)
				result = os.popen(command).read()
				print "*** Sent Command:", command + "\n"
				print "*** Received Result:", result + "\n"

			
			store_vll(digest, ap1Dpid)			
			# see the image one_hop for details on the switching label procedure
			
		else:
			# In the other cases we use a different approach for the rule; before we see the label
			# of the inport and outport of the same dpid; with more than one hop we see in general for
			# the forward rule the label of the inport on the next switch, while in the reverse rule the label of the inport on the 
			# previous switch. The previous approach is nested in a for loop, we use this loop in the middle dpid, while
			# we manage as special case the ingress/egress node, because the rules are different
			print "*** %s Hop Route" % (len(parsedResult)/2)
			# We manage first ingress/egress node
			print "*** Create Ingress Rules For LHS Of The Vll - %s" % (srcSwitch)
			# see the image more_than_one_hop for details on the switching label procedure
			ap1Dpid = parsedResult[0]['switch']
			ap1Port = parsedResult[0]['port']
			temp_key1 = ap1Dpid + "-" + str(ap1Port)
			tag1 = temp_sw_port_tag[temp_key1] 
			print "*** inKey: %s, inTag: %s" % (temp_key1, tag1)
			ap2Dpid = parsedResult[1]['switch']
			ap2Port = parsedResult[1]['port']
			temp_key2 = parsedResult[2]['switch'] + "-" + str(parsedResult[2]['port'])
			tag2 = temp_sw_port_tag[temp_key2]			
			print "*** outKey: %s, outTag: %s" % (temp_key2, tag2)
			print
			if tag1 == 0 and tag2 !=0:
				command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"vlan-id\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"set-vlan-id=%s,output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".f", "0xffff", ap1Port, tag2, ap2Port, controllerRestIp)
				result = os.popen(command).read()
				print "*** Sent Command:", command + "\n"
				print "*** Received Result:", result + "\n"
			elif tag1 != 0 and tag2 !=0:
				command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"vlan-id\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"set-vlan-id=%s,output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".f", tag1, ap1Port, tag2, ap2Port, controllerRestIp)
				result = os.popen(command).read()
				print "*** Sent Command:", command + "\n"
				print "*** Received Result:", result + "\n"
			else:
				print "Error Tag";
				sys.exit(-2)

			

			print "*** Create Egress Rules For LHS Of The Vll - %s" % (srcSwitch)
			temp_key2 = temp_key1
			tag2 = tag1
			temp_key1 = ap2Dpid + "-" + str(ap2Port)
			tag1 = temp_sw_port_tag[temp_key1]
			print "*** inKey: %s, inTag: %s" % (temp_key1, tag1)
			print "*** outKey: %s, outTag: %s" % (temp_key2, tag2)
			print
			if tag1 != 0 and tag2 ==0:
				command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"vlan-id\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"strip-vlan,output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".r", tag1, ap2Port, ap1Port, controllerRestIp)
				result = os.popen(command).read()
				print "*** Sent Command:", command + "\n"
				print "*** Received Result:", result + "\n"
			elif tag1 != 0 and tag2 !=0:
				command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"vlan-id\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"set-vlan-id=%s,output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".r", tag1, ap2Port, tag2, ap1Port, controllerRestIp)
				result = os.popen(command).read()
				print "*** Sent Command:", command + "\n"
				print "*** Received Result:", result + "\n"
			else:
				print "Error Tag";
				sys.exit(-2)
			
			store_vll(digest, ap1Dpid)
			
			print "*** Create Egress Rules For RHS Of The Vll - %s" % (dstSwitch)
			ap1Dpid = parsedResult[len(parsedResult)-2]['switch']
			ap1Port = parsedResult[len(parsedResult)-2]['port']
			temp_key1 = ap1Dpid + "-" + str(ap1Port)
			tag1 = temp_sw_port_tag[temp_key1] 
			print "*** inKey: %s, inTag: %s" % (temp_key1, tag1)
			ap2Dpid = parsedResult[len(parsedResult)-1]['switch']
			ap2Port = parsedResult[len(parsedResult)-1]['port']
			temp_key2 = ap2Dpid + "-" + str(ap2Port)
			tag2 = temp_sw_port_tag[temp_key2]
			print "*** outKey: %s, outTag: %s" % (temp_key2, tag2)
			print
			if tag1 != 0 and tag2 ==0:
				command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"vlan-id\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"strip-vlan,output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".f", tag1, ap1Port, ap2Port, controllerRestIp)
				result = os.popen(command).read()
				print "*** Sent Command:", command + "\n"
				print "*** Received Result:", result + "\n"
			elif tag1 != 0 and tag2 !=0:
				command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"vlan-id\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"set-vlan-id=%s,output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".f", tag1, ap1Port, tag2, ap2Port, controllerRestIp)
				result = os.popen(command).read()
				print "*** Sent Command:", command + "\n"
				print "*** Received Result:", result + "\n"
			else:
				print "Error Tag";
				sys.exit(-2)
			

			print "*** Create Ingress Rules For RHS Of The Vll - %s" % (dstSwitch)
			temp_key1 = parsedResult[len(parsedResult)-3]['switch'] + "-" + str(parsedResult[len(parsedResult)-3]['port'])
			tag1 = temp_sw_port_tag[temp_key1]
			print "*** inKey: %s, inTag: %s" % (temp_key2, tag2)
			print "*** outKey: %s, outTag: %s" % (temp_key1, tag1)
			print 
			if tag1 != 0 and tag2 ==0:
				command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"vlan-id\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"set-vlan-id=%s,output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".r", "0xffff", ap2Port, tag1, ap1Port, controllerRestIp)
				result = os.popen(command).read()
				print "*** Sent Command:", command + "\n"
				print "*** Received Result:", result + "\n"
			elif tag1 != 0 and tag2 !=0:
				command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"vlan-id\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"set-vlan-id=%s,output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".r", tag2, ap2Port, tag1, ap1Port, controllerRestIp)
				result = os.popen(command).read()
				print "*** Sent Command:", command + "\n"
				print "*** Received Result:", result + "\n"
			else:
				print "Error Tag";
				sys.exit(-2)
			store_vll(digest, ap1Dpid)



			# Now we manage the middle nodes
			for i in range(2, (len(parsedResult)-2)):
				print "index:", i
				if i % 2 == 0:
					ap1Dpid = parsedResult[i]['switch']
					ap1Port = parsedResult[i]['port']
					print ap1Dpid, ap1Port
				else:
					ap2Dpid = parsedResult[i]['switch']
					ap2Port = parsedResult[i]['port']
					print ap2Dpid, ap2Port

					print "*** Create Rules For %s" % ap1Dpid

					# send one flow mod per pair in route
					# using StaticFlowPusher rest API

					temp_key1 = ap1Dpid + "-" + str(ap1Port)
					tag1 = temp_sw_port_tag[temp_key1] 
					print "*** inKey: %s, inTag: %s" % (temp_key1, tag1)
					temp_key2 = parsedResult[i+1]['switch'] + "-" + str(parsedResult[i+1]['port'])
					tag2 = temp_sw_port_tag[temp_key2]			
					print "*** outKey: %s, outTag: %s" % (temp_key2, tag2)
					print
					command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"vlan-id\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"set-vlan-id=%s,output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".f", tag1, ap1Port, tag2, ap2Port, controllerRestIp)
					result = os.popen(command).read()
					print "*** Sent Command:", command + "\n"
					print "*** Received Result:", result + "\n"

					temp_key1 = ap2Dpid + "-" + str(ap2Port)
					tag1 = temp_sw_port_tag[temp_key1] 
					print "*** inKey: %s, inTag: %s" % (temp_key1, tag1)
					temp_key2 = parsedResult[i-2]['switch'] + "-" + str(parsedResult[i-2]['port'])
					tag2 = temp_sw_port_tag[temp_key2]			
					print "*** outKey: %s, outTag: %s" % (temp_key2, tag2)
					print
					command = "curl -s -d '{\"switch\": \"%s\", \"name\":\"%s\", \"vlan-id\":\"%s\", \"cookie\":\"0\", \"priority\":\"32768\", \"ingress-port\":\"%s\",\"active\":\"true\", \"actions\":\"set-vlan-id=%s,output=%s\"}' http://%s/wm/staticflowentrypusher/json | python -mjson.tool" % (ap1Dpid, ap1Dpid + "." + digest + ".r", tag1, ap2Port, tag2, ap1Port, controllerRestIp)
					result = os.popen(command).read()
					print "*** Sent Command:", command + "\n"
					print "*** Received Result:", result + "\n"
					store_vll(digest, ap1Dpid)

def del_command(args):
	print "*** Delete Vlls From Configuration File"

	print "*** Read Previous Vlls Inserted"
	if os.path.exists('vlls.json'):
		vllsDb = open('vlls.json','r')
		lines = vllsDb.readlines()
		vllsDb.close()
		vllsDb = open('vlls.json','w')
	else:
		lines={}
		print "*** No Vlls Inserted"
		return

	# Removing previously created flow from switches
	# using StaticFlowPusher rest API       
	# currently, circuitpusher records created circuits in local file ./circuits.db 
	# with circuit name and list of switches
	controllerRestIp = args.controllerRestIp

	for line in lines:
		data = json.loads(line)
		sw = data['Dpid']
		digest = data['name']
		print "*** Deleting Vll: %s - Switch %s" % (digest,sw)

		command = "curl -X DELETE -d '{\"name\":\"%s\", \"switch\":\"%s\"}' http://%s/wm/staticflowentrypusher/json 2> /dev/null | python -mjson.tool" % (sw + "." + digest + ".f", sw, controllerRestIp)
		result = os.popen(command).read()
		print "*** Sent Command:", command + "\n"
		print "*** Received Result:", result + "\n"

		command = "curl -X DELETE -d '{\"name\":\"%s\", \"switch\":\"%s\"}' http://%s/wm/staticflowentrypusher/json 2> /dev/null | python -mjson.tool" % (sw + "." + digest +".r", sw, controllerRestIp)
		result = os.popen(command).read()
		print "*** Sent Command:", command + "\n"
		print "*** Received Result:", result + "\n"

		
	
	vllsDb.close()

def run_command(data):
	if args.action == 'add':
		add_command(data)
	elif args.action == 'delete':
		del_command(data)
		

if __name__ == '__main__':
	args = parse_cmd_line()
	run_command(args)




