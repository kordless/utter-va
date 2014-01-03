### Stackmonkey VM Instance
This is the Stackmonkey VM, used by the stackmonkey.com service.  Stackmonkey VMs manage OpenStack clusters, allowing a provider to sell instances to end users for Bitcoin.

More information about Stackmonkey is available at: [http://stackmonkey.com](http://stackmonkey.com)

## Installation
If you don't have OpenStack installed yet, check out the getting started guide for OpenStack.

Launch a new Ubuntu 12.04.02 instance.  Use the following for your post install script:

    #!/bin/bash
    wget http://goo.gl/KJH5Sa -O - | sh