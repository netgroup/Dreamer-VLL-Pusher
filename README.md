![OSHI and DREAMER logos](http://netgroup.uniroma2.it/twiki/pub/Oshi/WebHome/dreamer-oshi-logo-github-2.png "http://netgroup.uniroma2.it/OSHI")

Dreamer-VLL-Pusher
==================

Virtual Leased Line Pusher 

For Floodlight OpenFlow Controller and RYU SDN Framework

Based On KcWang's CircuitPusher App

Using This Tool You Can Deploy Virtual Leased Lines (VLLs) or Pseudo Wires (PWs) in an OSHI Network. 

These services guarantee to the served end-points to be directly interconnected as if they were in the same Ethernet LAN.

This a result of the [DREAMER project](http://netgroup.uniroma2.it/DREAMER/).  
Addtional documentation is available at http://netgroup.uniroma2.it/OSHI/ .

License
=======

This sofware is licensed under the Apache License, Version 2.0.

Information can be found here:
 [Apache License 2.0](http://www.apache.org/licenses/LICENSE-2.0).

Tips
==============

The vll_pusher.py script depends on vll_pusher.cfg (here you have to store the OSHI endpoints and the ports of the virtual circuits, see the demo file). The virtual circuits, after an execution, are stored in the DB vlls.json, for now its execution is one shot.

There are two version of the script: 1) the first is for Floodlight 0.90 and leverages OpenFlow 1.0 capabilities in order to build the virtual circuits (in this case only the VLLs are created); 2) the second is for RYU controller and leverages OpenFlow 1.3 capabilities to build VLLs and PWs.

Docs
======

[Tag/Label Allocation](docs/vlan_tag_allocation.md)

Tips
==============

See [Dreamer-VLL-Pusher How-To](http://netgroup.uniroma2.it/twiki/bin/view/Oshi/OshiExperimentsHowto#VllPusher)

VLL Pusher Dependecies
=============================

0) FloodLight OpenFlow Controller [Floodlight Download Page](http://www.projectfloodlight.org/download/) (zip)

1) RYU SDN Framework [RYU Download Page](http://osrg.github.io/ryu/) (pip)

2) RYU patch (see RYU folder)

3) cURL (apt)

3) siphash (pip)

Todo
=====

1) Label Persistence




