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
import hashlib

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

# Derive From Node Name The DPID 
def convert_name_to_dpid(name):
	"Derive dpid from switch name, s1 -> 1"
        try:
		dpidLen = 16
		dpid = int( re.findall( r'\d+', name )[ 0 ] )
		dpid = hex( dpid )[ 2: ]
		dpid = '0' * ( dpidLen - len( dpid ) ) + dpid
		dpid = ':'.join(s.encode('hex') for s in dpid.decode('hex'))
		return dpid
        except IndexError:
            	raise Exception( 'Unable to derive default datapath ID - '
                             'please either specify a dpid or use a '
                             'canonical switch name such as s23.' )

# Read From vll_pusher.cfg The Configuration For The Vlls
# Each Line contains the configuration for the Vlls the format is: 
# LeftHandSideAOS|RightHandSideAOS|LeftHandSidePort|RightHandSidePort|LeftHandSideVID|RightHandSideVID|
def read_conf_file():
	print "*** Read Configuration File For Vll Pusher"
	path = "vll_pusher.cfg"
	if os.path.exists(path):
    		conf = open(path,'r')
    		lines = conf.readlines()
    		conf.close()
	else:
		print "No Configuration File Find In %s" % path
    		sys.exit(-2)

	# Parallel Arrays, with the same index we can access to the all vll information
	LHS_dpid= []
	RHS_dpid = []
	LHS_port = []
	RHS_port = []
	LHS_vlan_tag = []
	RHS_vlan_tag = []

	for line in lines:
		aoshis = line.split('|')
		# We discard local 'vll', i.e vll in the same l2 legacy network;
		# We manage them in Mininet with l2 switch vlan aware
		if aoshis[0] == aoshis[1] and aoshis[2] == aoshis[3]:
			print "Discard Local Tunnel"
		else: 
			dpid = aoshis[0]
			port = (aoshis[2])
			LHS_dpid.append(dpid)
			LHS_port.append(port)
			dpid = aoshis[1]
			port = (aoshis[3])
			RHS_dpid.append(dpid)
			RHS_port.append(port)
			LHS_vlan_tag.append(aoshis[4])
			RHS_vlan_tag.append(aoshis[5])

	print "*** LHS", LHS_dpid
	print "*** RHS", RHS_dpid
	print "*** LHS Port", LHS_port
	print "*** RHS Port", RHS_port	
	print "*** LHS Vlan Tag", LHS_vlan_tag	
	print "*** RHS Vlan Tag", RHS_vlan_tag
	return (LHS_dpid, RHS_dpid, LHS_port, RHS_port, LHS_vlan_tag, RHS_vlan_tag)

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

def convert_intf_to_port_number(LHS_dpid, LHS_port, RHS_dpid, RHS_port, controllerRestIP):
	global intf_to_port_number
	command = "curl -s http://%s/wm/core/controller/switches/json | python -mjson.tool" % (controllerRestIP)
	result = os.popen(command).read()
	parsedResult = json.loads(result)
	default = None	
	for i in range(0,len(LHS_dpid)):
		port_number = intf_to_port_number.get("%s-%s" % (LHS_dpid[i], LHS_port[i]), default)
		if port_number == None :
			for switch in parsedResult:
				if switch["dpid"] == LHS_dpid[i]:
					for port in switch["ports"]:
						if port["name"] == LHS_port[i]:
							port_number = str(port["portNumber"])
							intf_to_port_number["%s-%s" % (LHS_dpid[i], LHS_port[i])] = port_number
		LHS_port[i] = port_number

	for i in range(0,len(RHS_dpid)):
		port_number = intf_to_port_number.get("%s-%s" % (RHS_dpid[i], RHS_port[i]), default)
		if port_number == None :
			for switch in parsedResult:
				if switch["dpid"] == RHS_dpid[i]:
					for port in switch["ports"]:
						if port["name"] == RHS_port[i]:
							port_number = str(port["portNumber"])
							intf_to_port_number["%s-%s" % (RHS_dpid[i], RHS_port[i])] = port_number
		RHS_port[i] = port_number
	
	print intf_to_port_number
	return (LHS_dpid, LHS_port, RHS_dpid, RHS_port)
		
				
		





# Add Vlls Reading All the Information From Configuration File
def add_command(args):
	print "*** Add Vlls From Configuration File"

	print "*** Read Previous Vlls Inserted"
	if os.path.exists('./vlls.json'):
    		vllsDb = open('./vlls.json','r')
    		lines = vllsDb.readlines()
    		vllsDb.close()
	else:
    		lines={}
	
	(LHS_dpid, RHS_dpid, LHS_port, RHS_port, LHS_vlan_tag, RHS_vlan_tag) = read_conf_file()
	# We use this algorithm for the name generation	
	h = hashlib.new('ripemd160')
 	# Extract from cmd line options the controlller information
	controllerRestIp = args.controllerRestIp
	# Dictionary that stores the mapping port:next_label
	# We allocate the label using a counter, and we associate for each port used in this execution the next usable label
	# Probably in future we can add the persistence for the label
	sw_port_tag = {}
	(LHS_dpid, LHS_port, RHS_dpid, RHS_port) = convert_intf_to_port_number(LHS_dpid, LHS_port, RHS_dpid, RHS_port, controllerRestIp)
	# We can have more than one vlls
	for i in range(0, len(LHS_dpid)):
		# Retrieve the information
		srcSwitch = LHS_dpid[i]
		srcPort = LHS_port[i]
		dstSwitch = RHS_dpid[i]
		dstPort = RHS_port[i]
		lhs_vid = LHS_vlan_tag[i]
		rhs_vid = RHS_vlan_tag[i]
		print "*** Generate Name From VLL (%s-%s-%s) - (%s-%s-%s)" % (srcSwitch, srcPort, lhs_vid, dstSwitch, dstPort, rhs_vid)
		h.update(srcSwitch + "$" + srcPort + "$" + dstSwitch + "$" + dstPort + "$" + lhs_vid + "$" + rhs_vid)
		# Generate the name		
		digest = h.hexdigest()

		print "*** Vll Name", digest		
		
		vllExists = False
		
		# if the vll exists in the vllDb, we don't insert the flow
		for line in lines:
			data = json.loads(line)
			if data['name']==(digest):
				print "Vll %s exists already Skip" % digest
				vllExists = True
				break

		if vllExists == True:
			continue


		print "*** Create Vll:"
		print "*** From Source Device AOSHI %s Port %s" % (srcSwitch,srcPort)
		print "*** To Destination Device AOSHI %s port %s"% (dstSwitch,dstPort)

		# Retrieving route from source to destination
		# using Routing rest API

		command = "curl -s http://%s/wm/topology/route/%s/%s/%s/%s/json | python -mjson.tool" % (controllerRestIp, srcSwitch, srcPort, dstSwitch, dstPort)
		result = os.popen(command).read()
		parsedResult = json.loads(result)

		print
		print "*** Sent Command:", command + "\n"
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
		
		# We generate the labels associated for each port, while the ingress/egress and egress/ingress labels
		# come from the configuration file, because they depend on the local network choice
		for j in range(0, (len(parsedResult))):
			# Label for the LHS port
			if j == 0:
				temp_key1 = LHS_dpid[i] + "-" + str(LHS_port[i])
				temp_sw_port_tag[temp_key1] = int(LHS_vlan_tag[i])
				if sw_port_tag.get(temp_key1,default) <= int(LHS_vlan_tag[i]):
					sw_port_tag[temp_key1] = int(LHS_vlan_tag[i])
			# Label for the RHS port			
			elif j == (len(parsedResult)-1):
				temp_key1 = RHS_dpid[i] + "-" + str(RHS_port[i])
				temp_sw_port_tag[temp_key1] = int(RHS_vlan_tag[i])
				if sw_port_tag.get(temp_key1,default) <= int(RHS_vlan_tag[i]):
					sw_port_tag[temp_key1] = int(RHS_vlan_tag[i])			
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
			print "*** Create Ingress Rules For LHS Of The Vll - %s" % (LHS_dpid[i])
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

			

			print "*** Create Egress Rules For LHS Of The Vll - %s" % (LHS_dpid[i])
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
			
			print "*** Create Egress Rules For RHS Of The Vll - %s" % (RHS_dpid[i])
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
			

			print "*** Create Ingress Rules For RHS Of The Vll - %s" % (RHS_dpid[i])
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
	sys.stdout = open('vll_pusher.log', 'w')
	if args.action == 'add':
		add_command(data)
	elif args.action == 'delete':
		del_command(data)
		

if __name__ == '__main__':
	args = parse_cmd_line()
	run_command(args)




