## xov.io Virtual Appliance
This is the xov.io virtual appliance, used by providers to manage their OpenStack instances, allowing a provider to sell instances on a given comput pool exchange to end users for Bitcoin.

More information about the xov.io project is available at [http://xov.io](http://xov.io/) and the first xov.io pool, [StackMonkey](http://stackmonkey.com).

### Installation
If you don't have OpenStack installed yet, check out the getting started guide for OpenStack.

Launch a new Ubuntu 12.04.02 instance.  Use the following for your post install script:

    #!/bin/bash
    wget http://goo.gl/KJH5Sa -O - | sh

Login to the instance and run:

    cd /var/www/stackmonkey/
    ./resetdb.sh
