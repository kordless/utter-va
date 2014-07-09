## Welcome to Utter.io and StackMonkey!
Utter.io is like AirBnb for excess compute: The utter.io project provides fast location and provisioning of compute resources within a cooperative set of systems managed by [OpenStack](http://openstack.org/) operators. Resource accounting inside the network is settled with Bitcoin and purchases of compute instances can be made by users without an account. Additionally, groups of operators can form adhoc hybrid clouds, allowing fast scaling and sharing of excess compute resources between trusted entities.

The future of commodity compute can been seen by visiting the [StackMonkey compute pool](https://www.stackmonkey.com/). StackMonkey is the Wild West of compute pools and is intended for use by hackers, crackers, devs, and do-it-yourselfers.  This is where it all starts.

### Project Components
A set of three Open Source repositories provide the projects functionality: [utter-va](https://github.com/StackMonkey/utter-va), [utter-pool](https://github.com/StackMonkey/utter-pool) and [utter-exchange](https://github.com/StackMonkey/utter-exchange). The utter-va virtual appliance provided by this repository builds an instance which runs on top of an OpenStack cluster. The appliance controls the OpenStack cluster's capabilities, advertises other instances for sale on a central pool controller running utter-pool and launches instances when payments are observed on the the [Bitcoin Blockchain](https://en.bitcoin.it/wiki/Block_chain) through callbacks made by [Coinbase](https://coinbase.com/).

The first compute pool is hosted on [AppEngine](https://appspot.com) and runs at [StackMonkey](https://www.stackmonkey.com). The expected beta launch date of the StackMonkey pool is no later than July 31, 2014.  After launch, individuals will be able to purchase instances for Bitcoin from the site. Please note you will need an account on StackMonkey if you want to sell instances.

The utter-exchange component will be completed at a later date. The exchange will serve as a clearing house for compute put up for sale on the various pool controllers. The exchange will operate as a [DAC](https://en.bitcoin.it/wiki/Distributed_Autonomous_Community_/_Decentralized_Application) once the technologies required to create it have been completed.  You can expect a crypto currency to be launched for the project. Both the currency and compute assets managed by the network will be connected to the crypto markets.

### Requirements
The virtual appliance requires a running OpenStack cluster.  If you don't have an OpenStack cluster already running, fear not!  You may follow the instructions for [Installing OpenStack in 10 Minutes](http://www.stackgeek.com/guides/gettingstarted.html) on the [StackGeek website](http://stackgeek.com/).

Once you have OpenStack installed, you'll need to create or have the following service accounts available:

  - a [StackMonkey](https://www.stackmonkey.com/login/) account (signup takes 1 minute)
  - a [Coinbase](https://coinbase.com/signup?r=52a9c6bf937ab6453a00001e&utm_campaign=user-referral&src=referral-link) account (signup takes 2 minutes)
  - an [Ngrok](https://ngrok.com/) account (signup takes 1 minute)



### Automated Install
If you followed StackGeek's [Installing OpenStack in 10 Minutes](http://www.stackgeek.com/guides/gettingstarted.html) guide, you can run the [openstack_stackmonkey_va.sh](https://github.com/StackGeek/openstackgeek/blob/master/icehouse/openstack_stackmonkey_va.sh) script located in the [Icehouse](https://github.com/StackGeek/openstackgeek/tree/master/icehouse) directory to install the appliance:

    ./openstack_stackmonkey_va.sh

The script automatically creates a user and project for the virtual appliance, sets the security group rules for the project, and then launches the appliance on the OpenStack cluster.  SSH keys are automatically created for accessing the appliance's console and a URL will be output at the end for accessing the web UI.  

Once the script completes, you can skip to the configuration section below.

### Manual Install
If you already have OpenStack installed, you can manually start the virtual appliance by using a cloud init configuration:

    #cloud-config
    hostname: stackmonkey-va
    manage_etc_hosts: true
    runcmd:
     - [ wget, "http://goo.gl/KJH5Sa", -O, /tmp/install.sh ]
     - chmod 755 /tmp/install.sh
     - /tmp/install.sh


### Configuration
Once the instance has been started you can access the appliance's UI by entering the following into your browser (substituting the real IP address for this one):

    http://10.0.47.2/

### Video Guide
The [following video](https://vimeo.com/91805503) will step you through installing the virtual appliance on your OpenStack cluster.  If you have any questions about the install, you can head over the the [StackMonkey](https://www.stackmonkey.com/) site.

### Security

### Development
If you are doing development on this project, drop a file named **DEV** in the root directory to turn on the development debug configuration.

You'll also do manual starts of the service and Ngrok tunnel during development:

    ./manage.py serve
    ngrok -config tunnel.conf start utterio

Happy coding!