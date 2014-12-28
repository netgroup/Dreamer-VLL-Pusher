#!/usr/bin/python

import json
import argparse
import sys
import os
import siphash
import time
import binascii
from random import randrange

pusher_cfg = {}
intf_to_port_number = {}
port_number_to_mac = {}

# Utility function to read from configuration file the VLL to create
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

    for vll in pusher_cfg['vlls']:
        vll['lhs_dpid'] = vll['lhs_dpid'].replace(":","")
        vll['rhs_dpid'] = vll['rhs_dpid'].replace(":","")

    for pw in pusher_cfg['pws']:
        pw['lhs_dpid'] = pw['lhs_dpid'].replace(":","")
        pw['rhs_dpid'] = pw['rhs_dpid'].replace(":","")
        pw['lhs_mac'] = pw['lhs_mac'].replace(":","")
        pw['rhs_mac'] = pw['rhs_mac'].replace(":","")

    print "*** PUSHER_CFG", json.dumps(pusher_cfg, sort_keys=True, indent=4)

# Utility function for the vlls persisentce
def store_vll(name, dpid, table):
    # Store created vll attributes in local ./vlls.json
    datetime = time.asctime()
    vllParams = {'name': name, 'Dpid':dpid, 'datetime':datetime, 'table_id':table}
    stro = json.dumps(vllParams)
    vllsDb = open('./sr_vlls.json','a+')
    vllsDb.write(stro+"\n")
    vllsDb.close()

# Utility function for the pws persisentce
def store_pw(name, dpid, table):
    # Store created pw attributes in local ./pws.json
    datetime = time.asctime()
    pwParams = {'name': name, 'Dpid':dpid, 'datetime':datetime, 'table_id':table}
    stro = json.dumps(pwParams)
    pwsDb = open('./sr_pws.json','a+')
    pwsDb.write(stro+"\n")
    pwsDb.close()

# Utility function to translate intf name to port number
def retrieve_port_number_and_mac(controllerRestIP):

    global intf_to_port_number
    global port_number_to_mac

    command = "curl -s http://%s/v1.0/topology/switches | python -mjson.tool" % (controllerRestIP)
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
                            port_number = str(port["port_no"])
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
                            port_number = str(port["port_no"])
                            intf_to_port_number["%s-%s" % (rhs_dpid, rhs_intf)] = port_number
        vll['rhs_intf'] = port_number

    for pw in pusher_cfg['pws']:
        lhs_intf = pw['lhs_intf']
        lhs_dpid = pw['lhs_dpid']
        port_number = intf_to_port_number.get("%s-%s" % (lhs_dpid, lhs_intf), default)
        if port_number == None :
            for switch in parsedResult:
                if switch["dpid"] == lhs_dpid:
                    for port in switch["ports"]:
                        if port["name"] == lhs_intf:
                            port_number = str(port["port_no"])
                            intf_to_port_number["%s-%s" % (lhs_dpid, lhs_intf)] = port_number
        pw['lhs_intf'] = port_number

        rhs_intf = pw['rhs_intf']
        rhs_dpid = pw['rhs_dpid']
        port_number = intf_to_port_number.get("%s-%s" % (rhs_dpid, rhs_intf), default)
        if port_number == None :
            for switch in parsedResult:
                if switch["dpid"] == rhs_dpid:
                    for port in switch["ports"]:
                        if port["name"] == rhs_intf:
                            port_number = str(port["port_no"])
                            intf_to_port_number["%s-%s" % (rhs_dpid, rhs_intf)] = port_number
        pw['rhs_intf'] = port_number

    for switch in parsedResult:
        for port in switch["ports"]:
            dpid = str(port["dpid"])
            port_number = str(port["port_no"])
            port_number_to_mac["%s-%s"%(dpid, port_number)] = str(port["hw_addr"])

    print "*** PUSHER_CFG", json.dumps(pusher_cfg, sort_keys=True, indent=4)
    print "*** INTFS", json.dumps(intf_to_port_number, sort_keys=True, indent=4)
    print "*** MACS", json.dumps(port_number_to_mac, sort_keys=True, indent=4)

# Add Vlls Reading All the Information From Configuration File
def add_command(args):
	print "*** Add Vlls From Configuration File"

	print "*** Read Previous Vlls Inserted"
	if os.path.exists('./sr_vlls.json'):
		vllsDb = open('./sr_vlls.json','r')
		vlllines = vllsDb.readlines()
		vllsDb.close()
	else:
		vlllines={}

	if os.path.exists('./sr_pws.json'):
		pwsDb = open('./sr_pws.json','r')
		pwlines = pwsDb.readlines()
		pwsDb.close()
	else:
		pwlines={}

	read_conf_file()

	# We use this algorithm for the name generation    
	key = '0123456789ABCDEF'
	sip = siphash.SipHash_2_4(key)
	# Extract from cmd line options the controlller information
	controllerRestIp = args.controllerRestIp
	# Dictionary that stores the mapping port:next_label
	# We allocate the label using a counter, and we associate for each port used in this execution the next usable label
	# Probably in future we can add the persistence for the label
	sw_port_label = {}
	retrieve_port_number_and_mac(controllerRestIp)

	# Last 3 bits identify the SR-VLL TC
	# 0x40000 -> 010|0 0000 0000 0000 0000
	default_label_value = 262144
	# 0x5FFFF -> 010|1 1111 1111 1111 1111
	max_label_value = 393215

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
		cookie = sip.hash()
		cookie = str(cookie)


		print "*** Vll Name", cookie        

		vllExists = False

		# if the vll exists in the vllDb, we don't insert the flow
		for line in vlllines:
			data = json.loads(line)
			if data['name']==(cookie):
				print "Vll %s exists already Skip" % cookie
				vllExists = True
				break

		if vllExists == True:
			continue


		print "*** Create Vll:"
		print "*** From Source Device OSHI-PE %s Port %s" % (srcSwitch, srcPort)
		print "*** To Destination Device OSHI-PE %s port %s"% (dstSwitch, dstPort)

		# Retrieving route from source to destination
		# using Routing rest API

		command = "curl -s http://%s/v1.0/topology/route/%s/%s/%s/%s | python -mjson.tool" % (controllerRestIp, srcSwitch, srcPort, dstSwitch, dstPort)
		result = os.popen(command).read()
		parsedResult = json.loads(result)

		print
		#print "*** Sent Command:", command + "\n"        
		print "*** Received Result:", result + "\n"

		# Dictionary used for store the label of current vll
		temp_sw_port_label = {}

		if int(srcLabel) > max_label_value or int(dstLabel) > max_label_value:
			print "Ingress or Egress Label Not Allowable"
			sys.exit(-2)

		# We generate the labels associated for the Ingress and Egress Nodes
		for j in range(0, (len(parsedResult))):
			# Ingress Nodes
			if j == 0 and len(parsedResult) > 2:
				value = sw_port_label.get(srcSwitch, default_label_value)
				temp_sw_port_label[srcSwitch] = int(value)
				value = value + 1
				sw_port_label[srcSwitch] = value
			# Egress Nodes            
			elif j == (len(parsedResult)-1) and len(parsedResult) > 2:
				value = sw_port_label.get(dstSwitch, default_label_value)
				temp_sw_port_label[dstSwitch] = int(value)
				value = value + 1
				sw_port_label[dstSwitch] = value              

		print "*** Current Route Tag:"
		print json.dumps(temp_sw_port_label, sort_keys=True, indent=4)
		print
		print "*** Global Routes Tag:"
		print json.dumps(sw_port_label, sort_keys=True, indent=4)
		print

		# Manage the special case of one hop
		if len(parsedResult) == 2:
			print "*** One Hop Route"
			# The Switch, where we insert the rule
			ap1Dpid = parsedResult[0]['switch']
			# In port
			ap1Port = str(parsedResult[0]['port'])
			# ap1Dpid == ap2Dpid            
			ap2Dpid = parsedResult[1]['switch']
			# Out port
			ap2Port = str(parsedResult[1]['port'])

			# Forward's Rule
			command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\"}, \"actions\":[{\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableIP'], int(ap1Port, 16), int(ap2Port, 16), controllerRestIp)
			result = os.popen(command).read()
			print "*** Sent Command:", command + "\n"

			# Reverse Forward's Rule
			command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\"}, \"actions\":[{\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableIP'], int(ap2Port, 16), int(ap1Port, 16), controllerRestIp)
			result = os.popen(command).read()
			print "*** Sent Command:", command + "\n"              

			store_vll(cookie, ap1Dpid, pusher_cfg['tableIP'])            
			# see the image one_hop for details on the switching label procedure

		elif (len(parsedResult)) >= 2:
			print "*** %s Hop Route" % (len(parsedResult)/2)

			ingressDpid = parsedResult[0]['switch']
			ingressPort = parsedResult[0]['port']

			egressDpid = parsedResult[len(parsedResult)-1]['switch']
			egressPort = parsedResult[len(parsedResult)-1]['port']

			routeDpid = []	

			for i in range(0, (len(parsedResult)-1)):
				if parsedResult[i]['switch'] not in routeDpid:
					routeDpid.append(parsedResult[i]['switch'])

			index_fw_middle = randrange(len(routeDpid))
			middlefwDpid = parsedResult[index_fw_middle]['switch']
			print "*** Forward Path: %s - > %s -> %s" % (ingressDpid, middlefwDpid, egressDpid);
		
			labelfw1 = temp_sw_port_label[egressDpid]
			labelfw2 = get_vll_label_from_dpid(egressDpid)
			labelfw3 = get_vll_label_from_dpid(middlefwDpid)
			print "*** Forward Path Label Stack: |%s|%s|%s|" %(labelfw1, labelfw2, labelfw3)

			index_rv_middle = randrange(len(routeDpid))
			middlervDpid = parsedResult[index_rv_middle]['switch']
			print "*** Reverse Path: %s - > %s -> %s" % (egressDpid, middlervDpid, ingressDpid);
		
			labelrv1 = temp_sw_port_label[ingressDpid]
			labelrv2 = get_vll_label_from_dpid(ingressDpid)
			labelrv3 = get_vll_label_from_dpid(middlervDpid)
			print "*** Reverse Path Label Stack: |%s|%s|%s|" %(labelrv1, labelrv2, labelrv3)
			print

			print "*** Install Ingress Rules (FW) - LHS"
			# Ingress Rule For IP
			command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\"}, \"actions\":[{\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"GOTO_TABLE\", \"table_id\":%d}]}' http://%s/stats/flowentry/add" % (int(ingressDpid, 16), cookie, pusher_cfg['tableIP'], int(ingressPort, 16), "2048", "34887", labelfw1, "34887", labelfw2, "34887", labelfw3, pusher_cfg['tableSBP'], controllerRestIp)
			result = os.popen(command).read()
			print "*** Sent Command:", command + "\n"
			
			# Ingress Rule For ARP
			command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\"}, \"actions\":[{\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"GOTO_TABLE\", \"table_id\":%d}]}' http://%s/stats/flowentry/add" % (int(ingressDpid, 16), cookie, pusher_cfg['tableIP'], int(ingressPort, 16), "2054", "34888", labelfw1, "34888", labelfw2, "34888", labelfw3, pusher_cfg['tableSBP'], controllerRestIp)
			result = os.popen(command).read()
			print "*** Sent Command:", command + "\n"
			store_vll(cookie, ingressDpid, pusher_cfg['tableIP'])

			print "Install Egress Rules (RV) - LHS"
			# Rule For IP
			command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"eth_type\":\"%s\", \"mpls_label\":\"%s\", \"mpls_bos\":\"1\"}, \"actions\":[{\"type\":\"POP_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ingressDpid, 16), cookie, pusher_cfg['tableSBP'], "34887", labelrv1, "2048", int(ingressPort, 16), controllerRestIp)
			result = os.popen(command).read()
			print "*** Sent Command:", command + "\n"

			# Rule For ARP
			command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"eth_type\":\"%s\", \"mpls_label\":\"%s\", \"mpls_bos\":\"1\"}, \"actions\":[{\"type\":\"POP_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ingressDpid, 16), cookie, pusher_cfg['tableSBP'], "34888", labelrv1, "2054", int(ingressPort, 16), controllerRestIp)
			result = os.popen(command).read()
			print "*** Sent Command:", command + "\n"
			
			store_vll(cookie, ingressDpid, pusher_cfg['tableSBP'])

			print "*** Install Ingress Rules (RV) - RHS"
			# Ingress Rule For IP
			command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\"}, \"actions\":[{\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"GOTO_TABLE\", \"table_id\":%d}]}' http://%s/stats/flowentry/add" % (int(egressDpid, 16), cookie, pusher_cfg['tableIP'], int(egressPort, 16), "2048", "34887", labelrv1, "34887", labelrv2, "34887", labelrv3, pusher_cfg['tableSBP'], controllerRestIp)
			result = os.popen(command).read()
			print "*** Sent Command:", command + "\n"
			
			# Ingress Rule For ARP
			command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\"}, \"actions\":[{\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"GOTO_TABLE\", \"table_id\":%d}]}' http://%s/stats/flowentry/add" % (int(egressDpid, 16), cookie, pusher_cfg['tableIP'], int(egressPort, 16), "2054", "34888", labelrv1, "34888", labelrv2, "34888", labelrv3, pusher_cfg['tableSBP'], controllerRestIp)
			result = os.popen(command).read()
			print "*** Sent Command:", command + "\n"
			store_vll(cookie, egressDpid, pusher_cfg['tableIP'])

			print "Install Egress Rules (RV) - RHS"
	
			# Rule For IP
			command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"eth_type\":\"%s\", \"mpls_label\":\"%s\", \"mpls_bos\":\"1\"}, \"actions\":[{\"type\":\"POP_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(egressDpid, 16), cookie, pusher_cfg['tableSBP'], "34887", labelfw1, "2048", int(egressPort, 16), controllerRestIp)
			result = os.popen(command).read()
			print "*** Sent Command:", command + "\n"

			# Rule For ARP
			command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"eth_type\":\"%s\", \"mpls_label\":\"%s\", \"mpls_bos\":\"1\"}, \"actions\":[{\"type\":\"POP_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(egressDpid, 16), cookie, pusher_cfg['tableSBP'], "34888", labelfw1, "2054", int(egressPort, 16), controllerRestIp)
			result = os.popen(command).read()
			print "*** Sent Command:", command + "\n"
			
			store_vll(cookie, egressDpid, pusher_cfg['tableSBP'])
			print

def get_vll_label_from_dpid(dpid):
	LABEL_MASK=0x0FFFF
	LABEL_VLL=0x080000
	temp = dpid.replace(":","")
	temp = temp[8:]
	loopback = int(temp,16)
	label = (loopback & LABEL_MASK) | LABEL_VLL
	return label 
	
def get_pw_label_from_dpid(dpid):
	LABEL_MASK=0x0FFFF
	LABEL_PW=0x090000
	temp = dpid.replace(":","")
	temp = temp[8:]
	loopback = int(temp,16)
	label = (loopback & LABEL_MASK) | LABEL_PW
	return label

def del_command(data):
	print "*** Delete Saved Vlls and PWs"

	print "*** Read Previous Vlls Inserted"
	if os.path.exists('sr_vlls.json'):
		vllsDb = open('sr_vlls.json','r')
		lines = vllsDb.readlines()
		vllsDb.close()
		vllsDb = open('sr_vlls.json','w')
		
		# Removing previously created flow from switches
    	# using StaticFlowPusher rest API       
    	# currently, circuitpusher records created circuits in local file ./circuits.db 
    	# with circuit name and list of switches
		controllerRestIp = args.controllerRestIp

		for line in lines:
			data = json.loads(line)
			sw = data['Dpid']
			cookie = data['name']
			table = data['table_id']

			print "*** Deleting Vll: %s - Switch %s" % (cookie, sw)
			command = "curl -s -d '{\"cookie\":\"%s\", \"cookie_mask\":\"%s\", \"table_id\":%d, \"dpid\":\"%s\"}' http://%s/stats/flowentry/delete 2> /dev/null" % (cookie, (-1 & 0xFFFFFFFFFFFFFFFF), table, int(sw, 16), controllerRestIp)
			result = os.popen(command).read()
			print "*** Sent Command:", command + "\n"		

	
		vllsDb.close()
	else:
		lines={}
		print "*** No Vlls Inserted"
		#return

	print "*** Read Previous Pws Inserted"
	if os.path.exists('sr_pws.json'):
		pwsDb = open('sr_pws.json','r')
		lines = pwsDb.readlines()
		pwsDb.close()
		pwsDb = open('sr_pws.json','w')

		# Removing previously created flow from switches
    	# using StaticFlowPusher rest API       
    	# currently, circuitpusher records created circuits in local file ./circuits.db 
    	# with circuit name and list of switches
		controllerRestIp = args.controllerRestIp

		for line in lines:
			data = json.loads(line)
			sw = data['Dpid']
			cookie = data['name']
			table = data['table_id']

			print "*** Deleting Pw: %s - Switch %s" % (cookie, sw)
			command = "curl -s -d '{\"cookie\":\"%s\", \"cookie_mask\":\"%s\", \"table_id\":%d, \"dpid\":\"%s\"}' http://%s/stats/flowentry/delete 2> /dev/null" % (cookie, (-1 & 0xFFFFFFFFFFFFFFFF), table, int(sw, 16), controllerRestIp)
			result = os.popen(command).read()
			print "*** Sent Command:", command + "\n"		

		pwsDb.close()

	else:
		lines={}
		print "*** No Pws Inserted"
		#return

def run_command(data):
    if args.action == 'add':
        add_command(data)
    elif args.action == 'delete':
        del_command(data)

def parse_cmd_line():
    parser = argparse.ArgumentParser(description='Segment Routing Virtual Leased Line Pusher')
    parser.add_argument('--controller', dest='controllerRestIp', action='store', default='localhost:8080', help='controller IP:RESTport, e.g., localhost:8080 or A.B.C.D:8080')
    parser.add_argument('--add', dest='action', action='store_const', const='add', default='add', help='action: add')
    parser.add_argument('--delete', dest='action', action='store_const', const='delete', default='add', help='action: delete')
    args = parser.parse_args()    
    if len(sys.argv)==1:
            parser.print_help()
            sys.exit(1)    
    return args

if __name__ == '__main__':
    args = parse_cmd_line()
    run_command(args)
