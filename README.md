## xov.io Virtual Appliance
This is the xov.io virtual appliance, used by providers to manage their OpenStack instances.  The appliance runs inside an OpenStack cluster and allows a provider to sell instances on a given compute pool exchange to end users for Bitcoin.  It can also be used to share compute resources between trusted entities.

More information about the xov.io project works can be seen on the first compute pool running at [StackMonkey.com](https://www.stackmonkey.com).

### Installation
If you don't have OpenStack installed yet, follow [StackGeek's](http://www.stackgeek.com/) [Install OpenStack in 10 Minutes](http://www.stackgeek.com/guides/gettingstarted.html) guide. Once you've gotten OpenStack running, you'll run the [openstack_stackmonkey_va.sh]() script located in the **Grizzly** directory.

    ./openstack_stackmonkey_va.sh

The script installs a project, user, and security group rules for the virtual appliance.  It also starts a new instance named **StackMonkey VA** and adds a SSH keypair called **stackmonkey** to the project.

You can manually start the virtual appliance by entering the following two lines into the post creation field in the OpenStack Horizon UI:

    #!/bin/bash
    wget http://goo.gl/KJH5Sa -O - | sh

Once the instance has been started, you can access the appliance's UI by entering the following into your browser (substituting the IP address, of course):

    http://10.0.47.2/

### Video Guide
The following video will step you through installing the virtual appliance on your OpenStack cluster.  If you have any questions about the install, you can head over the the [StackMonkey](https://www.stackmonkey.com/) site.

