![Alt text](repo_data/dreamer-logo.png "Optional title")

Dreamer-VLL-Pusher
==================

Virtual Leased Line Pusher - Dreamer Project (GÉANT Open Call)
For OpenFlow Controller Floodlights 

Based On KcWang's CircuitPusher App

Using This Tool You Can Deploy A Virtual Leased Line In
Your Network. 

This service guarantees to the served end-points to be directly
interconnected as if they were in the same Ethernet LAN.

License
=======

This sofware is licensed under the Apache License, Version 2.0.

Information can be found here:
 [Apache License 2.0](http://www.apache.org/licenses/LICENSE-2.0).

Tips
==============

The Vll_Pusher depends on vll_pusher.cfg (here you have to store the OSHI endpoints and the ports). The Vlls, after an execution are stored in the DB vlls.json, for now its execution is one shot.

Docs
======

[VLAN Tag Allocation](docs/vlan_tag_allocation.md)

Tips
==============

See [Dreamer-VLL-Pusher How-To](http://netgroup.uniroma2.it/twiki/bin/view/Oshi/OshiExperimentsHowto#VllPusher)

VLL Pusher Dependecies
=============================

0) FloodLight Controller [Floodlight Download Page](http://www.projectfloodlight.org/download/) (zip)

1) cURL (apt)

Todo
=====

1) Label Persistence




