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

The Vll_Pusher Depends On vll_pusher.cfg. This File Should Be Created By The [x] Deployer
(x = Mininet Deployer, TestBeds Deployer). You Can Create Manually Your CFG, But Be Careful. 

The Vlls After An Execution Are Stored In The DB vlls.json

For Now Its Execution Is One Shot

Docs
======

[VLAN Tag Allocation](docs/vlan_tag_allocation.md)

VLL Pusher Dependecies
=============================
0) FloodLight Controller

Usage
=====

./vll_pusher.py [-h] [--controller CONTROLLERRESTIP] [--add] [--delete]

optional arguments:

  -h, --help            show this help message and exit

  --controller CONTROLLERRESTIP controller IP:RESTport

		1) localhost:8080

        2) A.B.C.D:8080

  --add action: add

  --delete action: delete

Todo
=====

1) Label Persistence




