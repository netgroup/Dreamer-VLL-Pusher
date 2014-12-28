#!/usr/bin/python

import json
import argparse
import sys
import os
import siphash
import time
import binascii

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
    vllsDb = open('./vlls.json','a+')
    vllsDb.write(stro+"\n")
    vllsDb.close()

# Utility function for the pws persisentce
def store_pw(name, dpid, table):
    # Store created pw attributes in local ./pws.json
    datetime = time.asctime()
    pwParams = {'name': name, 'Dpid':dpid, 'datetime':datetime, 'table_id':table}
    stro = json.dumps(pwParams)
    pwsDb = open('./pws.json','a+')
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
    if os.path.exists('./vlls.json'):
            vllsDb = open('./vlls.json','r')
            vlllines = vllsDb.readlines()
            vllsDb.close()
    else:
            vlllines={}

    if os.path.exists('./pws.json'):
            pwsDb = open('./pws.json','r')
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

        # We insert the rule each two json item, because floodlight's getRoute for each dpid, provides
        # A couple of item the in/out port and the out/in port for the rules forward/reverse - see the
        # output of the previous command 
        temp_key1 = None
        temp_key2 = None
        temp_label1 = None
        temp_label2 = None
        ap1Dpid = None
        ap1Port = None
        ap2Dpid = None
        ap2Port = None

        default = 16
        max_value = 131071

        if int(srcLabel) > max_value or int(dstLabel) > max_value:
			print "Ingress or Egress Label Not Allowable"
			sys.exit(-2)

		
        
        # We generate the labels associated for each port, while the ingress/egress and egress/ingress labels
        # come from the configuration file, because they depend on the local network choice
        for j in range(0, (len(parsedResult))):
            # Label for the LHS port
            if j == 0:
                temp_key1 = srcSwitch + "-" + srcPort
                temp_sw_port_label[temp_key1] = int(srcLabel)
                if sw_port_label.get(temp_key1,default) <= int(srcLabel):
                    sw_port_label[temp_key1] = int(srcLabel)
            # Label for the RHS port            
            elif j == (len(parsedResult)-1):
                temp_key1 = dstSwitch + "-" + dstPort
                temp_sw_port_label[temp_key1] = int(dstLabel)
                if sw_port_label.get(temp_key1,default) <= int(dstLabel):
                    sw_port_label[temp_key1] = int(dstLabel)            
            # Middle ports            
            elif (j > 0 and j < (len(parsedResult)-1)):
                apDPID = parsedResult[j]['switch']
                apPORT = parsedResult[j]['port']
                temp_key1 = apDPID + "-" + str(apPORT)
                value = sw_port_label.get(temp_key1, default)
                temp_sw_port_label[temp_key1] = value
                value = value + 1
                sw_port_label[temp_key1] = value            

        
        
        
        print "*** Current Route Label:"
        print json.dumps(temp_sw_port_label, sort_keys=True, indent=4)
        print
        print "*** Global Routes Label:"
        print json.dumps(sw_port_label, sort_keys=True, indent=4)
        print             
        
        
        # Manage the special case of one hop
        if len(parsedResult) == 2:
            print "*** One Hop Route"
            # The Switch, where we insert the rule
            ap1Dpid = parsedResult[0]['switch']
            # In port
            ap1Port = str(parsedResult[0]['port'])
            temp_key1 = ap1Dpid + "-" + ap1Port
            label1 = temp_sw_port_label[temp_key1]
            # ap1Dpid == ap2Dpid            
            ap2Dpid = parsedResult[1]['switch']
            # Out port
            ap2Port = str(parsedResult[1]['port'])
            temp_key2 = ap2Dpid + "-" + ap2Port
            label2 = temp_sw_port_label[temp_key2]

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
            label1 = temp_sw_port_label[temp_key1] 
            print "*** inKey: %s, inLabel: %s" % (temp_key1, label1)
            ap2Dpid = parsedResult[1]['switch']
            ap2Port = parsedResult[1]['port']
            temp_key2 = parsedResult[2]['switch'] + "-" + str(parsedResult[2]['port'])
            label2 = temp_sw_port_label[temp_key2]            
            print "*** outKey: %s, outLabel: %s" % (temp_key2, label2)
            print

			# Rule For IP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\"}, \"actions\":[{\"type\":\"GOTO_TABLE\", \"table_id\":%d}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableIP'], int(ap1Port, 16), "2048", pusher_cfg['tableSBP'], controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"
			
            # Rule For ARP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\"}, \"actions\":[{\"type\":\"GOTO_TABLE\", \"table_id\":%d}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableIP'], int(ap1Port, 16), "2054", pusher_cfg['tableSBP'], controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"
            store_vll(cookie, ap1Dpid, pusher_cfg['tableIP'])

			# Rule For IP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\"}, \"actions\":[{\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap1Port, 16), "2048", "34887", label2, int(ap2Port, 16), controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"
			
            # Rule For ARP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\"}, \"actions\":[{\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap1Port, 16), "2054", "34888", label2, int(ap2Port, 16), controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"

            print "*** Create Egress Rules For LHS Of The Vll - %s" % (srcSwitch)
            temp_key2 = temp_key1
            label2 = label1
            temp_key1 = ap2Dpid + "-" + str(ap2Port)
            label1 = temp_sw_port_label[temp_key1]
            print "*** inKey: %s, inLabel: %s" % (temp_key1, label1)
            print "*** outKey: %s, outLabel: %s" % (temp_key2, label2)
            print

			# Rule For IP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\", \"mpls_label\":\"%s\"}, \"actions\":[{\"type\":\"POP_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap2Port, 16), "34887", label1, "2048", int(ap1Port, 16), controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"

			# Rule For ARP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\", \"mpls_label\":\"%s\"}, \"actions\":[{\"type\":\"POP_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap2Port, 16), "34888", label1, "2054", int(ap1Port, 16), controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"
      
            store_vll(cookie, ap1Dpid, pusher_cfg['tableSBP'])
            
            print "*** Create Egress Rules For RHS Of The Vll - %s" % (dstSwitch)
            ap1Dpid = parsedResult[len(parsedResult)-2]['switch']
            ap1Port = parsedResult[len(parsedResult)-2]['port']
            temp_key1 = ap1Dpid + "-" + str(ap1Port)
            label1 = temp_sw_port_label[temp_key1] 
            print "*** inKey: %s, inLabel: %s" % (temp_key1, label1)
            ap2Dpid = parsedResult[len(parsedResult)-1]['switch']
            ap2Port = parsedResult[len(parsedResult)-1]['port']
            temp_key2 = ap2Dpid + "-" + str(ap2Port)
            label2 = temp_sw_port_label[temp_key2]
            print "*** outKey: %s, outLabel: %s" % (temp_key2, label2)
            print
            
			# Rule For IP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\", \"mpls_label\":\"%s\"}, \"actions\":[{\"type\":\"POP_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap1Port, 16), "34887", label1, "2048", int(ap2Port, 16), controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"

			# Rule For ARP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\", \"mpls_label\":\"%s\"}, \"actions\":[{\"type\":\"POP_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap1Port, 16), "34888", label1, "2054", int(ap2Port, 16), controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"
            
            print "*** Create Ingress Rules For RHS Of The Vll - %s" % (dstSwitch)
            temp_key1 = parsedResult[len(parsedResult)-3]['switch'] + "-" + str(parsedResult[len(parsedResult)-3]['port'])
            label1 = temp_sw_port_label[temp_key1]
            print "*** inKey: %s, inLabel: %s" % (temp_key2, label2)
            print "*** outKey: %s, outLabel: %s" % (temp_key1, label1)
            print 

			# Rule For IP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\"}, \"actions\":[{\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap2Port, 16), "2048", "34887", label1, int(ap1Port, 16), controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"
			
			# Rule For ARP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\"}, \"actions\":[{\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap2Port, 16), "2054", "34888", label1, int(ap1Port, 16), controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"

            store_vll(cookie, ap1Dpid, pusher_cfg['tableSBP'])

			# Rule For IP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\"}, \"actions\":[{\"type\":\"GOTO_TABLE\", \"table_id\":%d}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableIP'], int(ap2Port, 16), "2048", pusher_cfg['tableSBP'], controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"
			
			# Rule For ARP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\"}, \"actions\":[{\"type\":\"GOTO_TABLE\", \"table_id\":%d}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableIP'], int(ap2Port, 16), "2054", pusher_cfg['tableSBP'], controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"

            store_vll(cookie, ap1Dpid, pusher_cfg['tableIP'])

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

                    temp_key1 = ap1Dpid + "-" + str(ap1Port)
                    label1 = temp_sw_port_label[temp_key1] 
                    print "*** inKey: %s, inLabel: %s" % (temp_key1, label1)
                    temp_key2 = parsedResult[i+1]['switch'] + "-" + str(parsedResult[i+1]['port'])
                    label2 = temp_sw_port_label[temp_key2]            
                    print "*** outKey: %s, outLabel: %s" % (temp_key2, label2)
                    print
					
					# Rule For IP
                    command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\", \"mpls_label\":\"%s\"}, \"actions\":[{\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap1Port, 16), "34887", label1, label2, int(ap2Port, 16), controllerRestIp)
                    result = os.popen(command).read()
                    print "*** Sent Command:", command + "\n"

					# Rule For ARP
                    command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\", \"mpls_label\":\"%s\"}, \"actions\":[{\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap1Port, 16), "34888", label1, label2, int(ap2Port, 16), controllerRestIp)
                    result = os.popen(command).read()
                    print "*** Sent Command:", command + "\n"

                    temp_key1 = ap2Dpid + "-" + str(ap2Port)
                    label1 = temp_sw_port_label[temp_key1] 
                    print "*** inKey: %s, inLabel: %s" % (temp_key1, label1)
                    temp_key2 = parsedResult[i-2]['switch'] + "-" + str(parsedResult[i-2]['port'])
                    label2 = temp_sw_port_label[temp_key2]            
                    print "*** outKey: %s, outLabel: %s" % (temp_key2, label2)
                    print

					# Rule For IP
                    command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\", \"mpls_label\":\"%s\"}, \"actions\":[{\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap2Port, 16), "34887", label1, label2, int(ap1Port, 16), controllerRestIp)
                    result = os.popen(command).read()
                    print "*** Sent Command:", command + "\n"

					# Rule For ARP
                    command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\", \"mpls_label\":\"%s\"}, \"actions\":[{\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap2Port, 16), "34888", label1, label2, int(ap1Port, 16), controllerRestIp)
                    result = os.popen(command).read()
                    print "*** Sent Command:", command + "\n"

                    store_vll(cookie, ap1Dpid, pusher_cfg['tableSBP'])
        else:
            print "Error Wrong Route"
            sys.exit(-2)

    
    # We can have more than one pws
    for pw in pusher_cfg['pws']:

        # Retrieve the information
        srcSwitch = pw['lhs_dpid']
        srcPort = pw['lhs_intf']
        dstSwitch = pw['rhs_dpid']
        dstPort = pw['rhs_intf']
        srcLabel = pw['lhs_label']
        dstLabel = pw['rhs_label']
        srcMAC = pw['lhs_mac']
        dstMAC = pw['rhs_mac']

        print "*** Generate Name From PW (%s-%s-%s-%s) - (%s-%s-%s-%s)" % (srcSwitch, srcPort, srcLabel, srcMAC, dstSwitch, dstPort, dstLabel, dstMAC)
        sip.update(srcSwitch + "$" + srcPort + "$" + srcLabel + "$" + srcMAC + "$" + dstSwitch + "$" + dstPort + "$" + dstLabel + "$" + dstMAC)
        # Generate the name        
        cookie = sip.hash()
        cookie = str(cookie)
        

        print "*** Pw Name", cookie        
        
        pwExists = False
        
        # if the pw exists in the pwDb, we don't insert the flow
        for line in pwlines:
            data = json.loads(line)
            if data['name']==(cookie):
                print "Pw %s exists already Skip" % cookie
                pwExists = True
                break

        if pwExists == True:
            continue


        print "*** Create Pw:"
        print "*** From Source Device OSHI-PE %s Port %s MAC %s" % (srcSwitch, srcPort, srcMAC)
        print "*** To Destination Device OSHI-PE %s port %s MAC %s"% (dstSwitch, dstPort, dstMAC)

        # Retrieving route from source to destination
        # using Routing rest API

        command = "curl -s http://%s/v1.0/topology/route/%s/%s/%s/%s | python -mjson.tool" % (controllerRestIp, srcSwitch, srcPort, dstSwitch, dstPort)
        result = os.popen(command).read()
        parsedResult = json.loads(result)

        print
        #print "*** Sent Command:", command + "\n"        
        print "*** Received Result:", result + "\n"


        # Dictionary used for store the label of current pw
        temp_sw_port_label = {}

        # We insert the rule each two json item, because floodlight's getRoute for each dpid, provides
        # A couple of item the in/out port and the out/in port for the rules forward/reverse - see the
        # output of the previous command 
        temp_key1 = None
        temp_key2 = None
        temp_label1 = None
        temp_label2 = None
        ap1Dpid = None
        ap1Port = None
        ap2Dpid = None
        ap2Port = None

        default = 131072
        max_value = 262143

        if int(srcLabel) > max_value or int(dstLabel) > max_value:
			print "Ingress or Egress Label Not Allowable"
			sys.exit(-2)

		
        
        # We generate the labels associated for each port
        for j in range(0, (len(parsedResult))):
            # Label for the LHS port
            if j == 0:
                temp_key1 = srcSwitch + "-" + srcPort
                temp_sw_port_label[temp_key1] = int(srcLabel)
                if sw_port_label.get(temp_key1,default) <= int(srcLabel):
                    sw_port_label[temp_key1] = int(srcLabel)
            # Label for the RHS port            
            elif j == (len(parsedResult)-1):
                temp_key1 = dstSwitch + "-" + dstPort
                temp_sw_port_label[temp_key1] = int(dstLabel)
                if sw_port_label.get(temp_key1,default) <= int(dstLabel):
                    sw_port_label[temp_key1] = int(dstLabel)            
            # Middle ports            
            else :
                apDPID = parsedResult[j]['switch']
                apPORT = parsedResult[j]['port']
                temp_key1 = apDPID + "-" + str(apPORT)
                value = sw_port_label.get(temp_key1, default)
                temp_sw_port_label[temp_key1] = value
                value = value + 1
                sw_port_label[temp_key1] = value            

        
        
        
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
            temp_key1 = ap1Dpid + "-" + ap1Port
            label1 = temp_sw_port_label[temp_key1]
            # ap1Dpid == ap2Dpid            
            ap2Dpid = parsedResult[1]['switch']
            # Out port
            ap2Port = str(parsedResult[1]['port'])
            temp_key2 = ap2Dpid + "-" + ap2Port
            label2 = temp_sw_port_label[temp_key2]

            # Forward's Rule
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\"}, \"actions\":[{\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableIP'], int(ap1Port, 16), int(ap2Port, 16), controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"
            
            # Reverse Forward's Rule
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\"}, \"actions\":[{\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableIP'], int(ap2Port, 16), int(ap1Port, 16), controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"              
     
            store_pw(cookie, ap1Dpid, pusher_cfg['tableIP'])            
            # see the image one_hop for details on the switching label procedure

        elif (len(parsedResult)) >= 2:
            # In the other cases we use a different approach for the rule; before we see the label
            # of the inport and outport of the same dpid; with more than one hop we see in general for
            # the forward rule the label of the inport on the next switch, while in the reverse rule the label of the inport on the 
            # previous switch. The previous approach is nested in a for loop, we use this loop in the middle dpid, while
            # we manage as special case the ingress/egress node, because the rules are different
            print "*** %s Hop Route" % (len(parsedResult)/2)
            # We manage first ingress/egress node
            print "*** Create Ingress Rules For LHS Of The Pw - %s" % (srcSwitch)
            # see the image more_than_one_hop for details on the switching label procedure
            ap1Dpid = parsedResult[0]['switch']
            ap1Port = parsedResult[0]['port']
            temp_key1 = ap1Dpid + "-" + str(ap1Port)
            label1 = temp_sw_port_label[temp_key1] 
            print "*** inKey: %s, inLabel: %s" % (temp_key1, label1)
            ap2Dpid = parsedResult[1]['switch']
            ap2Port = parsedResult[1]['port']
            temp_key2 = parsedResult[2]['switch'] + "-" + str(parsedResult[2]['port'])
            label2 = temp_sw_port_label[temp_key2]            
            print "*** outKey: %s, outLabel: %s" % (temp_key2, label2)
            print

            #match_mac = srcMAC
            src_mac = port_number_to_mac["%s-%s" %(ap2Dpid, ap2Port)]
            dst_mac = port_number_to_mac[temp_key2]

			# Rule For IP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\"}, \"actions\":[{\"type\":\"GOTO_TABLE\", \"table_id\":%d}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableIP'], int(ap1Port, 16), "2048", pusher_cfg['tableSBP'], controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"
            
            store_pw(cookie, ap1Dpid, pusher_cfg['tableIP'])

			# Rule For IP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\"}, \"actions\":[{\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"SET_FIELD\", \"field\":\"eth_src\", \"value\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"eth_dst\", \"value\":\"%s\"}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap1Port, 16), "2048", "34887", label2, src_mac, dst_mac, int(ap2Port, 16), controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"

            print "*** Create Egress Rules For LHS Of The Pw - %s" % (srcSwitch)
            temp_key2 = temp_key1
            label2 = label1
            temp_key1 = ap2Dpid + "-" + str(ap2Port)
            label1 = temp_sw_port_label[temp_key1]
            print "*** inKey: %s, inLabel: %s" % (temp_key1, label1)
            print "*** outKey: %s, outLabel: %s" % (temp_key2, label2)
            print

            match_mac = port_number_to_mac[temp_key1]
            src_mac = dstMAC
            dst_mac = srcMAC

			# Rule For IP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\", \"mpls_label\":\"%s\", \"dl_dst\":\"%s\"}, \"actions\":[{\"type\":\"POP_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"eth_src\", \"value\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"eth_dst\", \"value\":\"%s\"}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap2Port, 16), "34887", label1, match_mac, "2048", src_mac, dst_mac, int(ap1Port, 16), controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"
  
            store_pw(cookie, ap1Dpid, pusher_cfg['tableSBP'])
            
            print "*** Create Egress Rules For RHS Of The Pw - %s" % (dstSwitch)
            ap1Dpid = parsedResult[len(parsedResult)-2]['switch']
            ap1Port = parsedResult[len(parsedResult)-2]['port']
            temp_key1 = ap1Dpid + "-" + str(ap1Port)
            label1 = temp_sw_port_label[temp_key1] 
            print "*** inKey: %s, inLabel: %s" % (temp_key1, label1)
            ap2Dpid = parsedResult[len(parsedResult)-1]['switch']
            ap2Port = parsedResult[len(parsedResult)-1]['port']
            temp_key2 = ap2Dpid + "-" + str(ap2Port)
            label2 = temp_sw_port_label[temp_key2]
            print "*** outKey: %s, outLabel: %s" % (temp_key2, label2)
            print

            match_mac = port_number_to_mac[temp_key1]
            src_mac = srcMAC
            dst_mac = dstMAC
            
			# Rule For IP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\", \"mpls_label\":\"%s\", \"dl_dst\":\"%s\"}, \"actions\":[{\"type\":\"POP_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"eth_src\", \"value\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"eth_dst\", \"value\":\"%s\"}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap1Port, 16), "34887", label1, match_mac, "2048", src_mac, dst_mac, int(ap2Port, 16), controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"
            
            print "*** Create Ingress Rules For RHS Of The Pw - %s" % (dstSwitch)
            temp_key1 = parsedResult[len(parsedResult)-3]['switch'] + "-" + str(parsedResult[len(parsedResult)-3]['port'])
            label1 = temp_sw_port_label[temp_key1]
            print "*** inKey: %s, inLabel: %s" % (temp_key2, label2)
            print "*** outKey: %s, outLabel: %s" % (temp_key1, label1)
            print

            match_mac = dstMAC
            temp_key2 = ap1Dpid + "-" + str(ap1Port)
            src_mac = port_number_to_mac[temp_key2]
            dst_mac = port_number_to_mac[temp_key1] 

			# Rule For IP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\"}, \"actions\":[{\"type\":\"PUSH_MPLS\", \"ethertype\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"SET_FIELD\", \"field\":\"eth_src\", \"value\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"eth_dst\", \"value\":\"%s\"}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap2Port, 16), "2048", "34887", label1, src_mac, dst_mac, int(ap1Port, 16), controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"
			
            store_pw(cookie, ap1Dpid, pusher_cfg['tableSBP'])

			# Rule For IP
            command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\"}, \"actions\":[{\"type\":\"GOTO_TABLE\", \"table_id\":%d}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableIP'], int(ap2Port, 16), "2048", pusher_cfg['tableSBP'], controllerRestIp)
            result = os.popen(command).read()
            print "*** Sent Command:", command + "\n"
			
            store_pw(cookie, ap1Dpid, pusher_cfg['tableIP'])

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

                    temp_key1 = ap1Dpid + "-" + str(ap1Port)
                    label1 = temp_sw_port_label[temp_key1] 
                    print "*** inKey: %s, inLabel: %s" % (temp_key1, label1)
                    temp_key2 = parsedResult[i+1]['switch'] + "-" + str(parsedResult[i+1]['port'])
                    label2 = temp_sw_port_label[temp_key2]            
                    print "*** outKey: %s, outLabel: %s" % (temp_key2, label2)
                    print

                    match_mac = port_number_to_mac[ap1Dpid + "-" + str(ap1Port)]
                    src_mac = port_number_to_mac[ap2Dpid + "-" + str(ap2Port)]
                    dst_mac = port_number_to_mac[temp_key2] 
					
					# Rule For IP
                    command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\", \"mpls_label\":\"%s\", \"dl_dst\":\"%s\"}, \"actions\":[{\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s},  {\"type\":\"SET_FIELD\", \"field\":\"eth_src\", \"value\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"eth_dst\", \"value\":\"%s\"}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap1Port, 16), "34887", label1, match_mac, label2, src_mac, dst_mac, int(ap2Port, 16), controllerRestIp)
                    result = os.popen(command).read()
                    print "*** Sent Command:", command + "\n"

                    temp_key1 = ap2Dpid + "-" + str(ap2Port)
                    label1 = temp_sw_port_label[temp_key1] 
                    print "*** inKey: %s, inLabel: %s" % (temp_key1, label1)
                    temp_key2 = parsedResult[i-2]['switch'] + "-" + str(parsedResult[i-2]['port'])
                    label2 = temp_sw_port_label[temp_key2]            
                    print "*** outKey: %s, outLabel: %s" % (temp_key2, label2)
                    print

                    match_mac = port_number_to_mac[temp_key1]
                    src_mac = port_number_to_mac[ap1Dpid + "-" + str(ap1Port)]
                    dst_mac = port_number_to_mac[temp_key2]

					# Rule For IP
                    command = "curl -s -d '{\"dpid\": \"%s\", \"cookie\":\"%s\", \"priority\":\"32768\", \"table_id\":%d, \"match\":{\"in_port\":\"%s\", \"eth_type\":\"%s\", \"mpls_label\":\"%s\", \"dl_dst\":\"%s\"}, \"actions\":[{\"type\":\"SET_FIELD\", \"field\":\"mpls_label\", \"value\":%s}, {\"type\":\"SET_FIELD\", \"field\":\"eth_src\", \"value\":\"%s\"}, {\"type\":\"SET_FIELD\", \"field\":\"eth_dst\", \"value\":\"%s\"}, {\"type\":\"OUTPUT\", \"port\":\"%s\"}]}' http://%s/stats/flowentry/add" % (int(ap1Dpid, 16), cookie, pusher_cfg['tableSBP'], int(ap2Port, 16), "34887", label1, match_mac,  label2, src_mac, dst_mac, int(ap1Port, 16), controllerRestIp)
                    result = os.popen(command).read()
                    print "*** Sent Command:", command + "\n"

                    store_pw(cookie, ap1Dpid, pusher_cfg['tableSBP'])
        else:
            print "Error Wrong Route"
            sys.exit(-2)

    
def del_command(data):
	print "*** Delete Saved Vlls and PWs"

	print "*** Read Previous Vlls Inserted"
	if os.path.exists('vlls.json'):
		vllsDb = open('vlls.json','r')
		lines = vllsDb.readlines()
		vllsDb.close()
		vllsDb = open('vlls.json','w')
		
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
	if os.path.exists('pws.json'):
		pwsDb = open('pws.json','r')
		lines = pwsDb.readlines()
		pwsDb.close()
		pwsDb = open('pws.json','w')

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
    parser = argparse.ArgumentParser(description='Virtual Leased Line Pusher')
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
