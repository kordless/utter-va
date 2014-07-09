## Welcome to Utter.io and StackMonkey!
Utter.io is like AirBnb for excess compute: The utter.io project provides fast location and provisioning of compute resources within a cooperative set of systems managed by [OpenStack](http://openstack.org/) operators. Resource accounting inside the network is settled with Bitcoin and purchases of compute instances can be made by users without an account. Additionally, groups of operators can form adhoc hybrid clouds, allowing fast scaling and sharing of excess compute resources between trusted entities.

The future of commodity compute can been seen by visiting the [StackMonkey compute pool](https://www.stackmonkey.com/). StackMonkey is intended to be the Wild West of Utter.io compute pools and is intended for use by hackers, crackers, devs, and do-it-yourselfers.  This is where it all starts.

### Project Components
A set of three Open Source repositories provide the project's functionality: [utter-va](https://github.com/StackMonkey/utter-va), [utter-pool](https://github.com/StackMonkey/utter-pool) and [utter-exchange](https://github.com/StackMonkey/utter-exchange). The utter-va virtual appliance provided by this repository builds an instance which runs on top of an OpenStack cluster. The appliance controls the OpenStack cluster's capabilities, advertises other instances for sale on a central pool controller running utter-pool and launches instances when payments are observed on the the [Bitcoin Blockchain](https://en.bitcoin.it/wiki/Block_chain) through callbacks made by [Coinbase](https://coinbase.com/).

The first compute pool is hosted on [AppEngine](https://appspot.com) and runs at [StackMonkey](https://www.stackmonkey.com). The expected beta launch date of the StackMonkey pool is no later than **July 31, 2014**.  After launch, individuals will be able to purchase instances for Bitcoin from the site. Please note you will need an account on StackMonkey if you want to sell instances.

The utter-exchange component will be completed at a later date. The exchange will serve as a clearing house for compute put up for sale on the various pool controllers. The exchange will operate as a [DAC](https://en.bitcoin.it/wiki/Distributed_Autonomous_Community_/_Decentralized_Application) once the technologies required to create it have been completed.  You can expect a crypto currency to be launched for the project. Both the currency and compute assets managed by the network will be connected to the crypto markets.

### Requirements
The virtual appliance requires a running OpenStack cluster.  If you don't have an OpenStack cluster already running, fear not!  You may follow the instructions for [Installing OpenStack in 10 Minutes](http://www.stackgeek.com/guides/gettingstarted.html) on the [StackGeek website](http://stackgeek.com/).

Once you have OpenStack installed, you'll need to create or have the following service accounts available:

  - a [StackMonkey](https://www.stackmonkey.com/login/) account (signup takes 1 minute)
  - a [Coinbase](https://coinbase.com/signup?r=52a9c6bf937ab6453a00001e&utm_campaign=user-referral&src=referral-link) account (signup takes 2 minutes)
  - an [Ngrok](https://ngrok.com/) account (signup takes 1 minute)


### Watch the Video
The [following video](https://vimeo.com/91805503) will step you through installing the virtual appliance on your OpenStack cluster.  If you have any questions about the install, you can head over the the [StackMonkey](https://www.stackmonkey.com/) site.

### Automated Install
If you followed StackGeek's [Installing OpenStack in 10 Minutes](http://www.stackgeek.com/guides/gettingstarted.html) guide, you can run the [openstack_stackmonkey_va.sh](https://github.com/StackGeek/openstackgeek/blob/master/icehouse/openstack_stackmonkey_va.sh) script located in the [Icehouse](https://github.com/StackGeek/openstackgeek/tree/master/icehouse) directory to install the appliance:

    ./openstack_stackmonkey_va.sh

The script automatically creates a user and project for the virtual appliance, sets the security group rules for the project, and then launches the appliance on the OpenStack cluster.  SSH keys are automatically created for accessing the appliance's console and a URL will be spit out at the end for accessing the web UI.  

Once the script completes, you can skip to the configuration section below.

### Manual Install
If you have previously installed OpenStack, you can manually start a virtual appliance from the Horizon UI.  Begin by logging into OpenStack with an administrative account and then following these steps:

  - Click on the **Admin** tab to the far left and then click on **Identity..Projects**. To the right, click on the **Create Project** button and then create a new project called **StackMonkey**.
  - Back in the **Admin** panel, click on **Users**.  To the right, click on the **Create User** button and then create a new user called **stackmonkey** and set the user's password.  Set the role of the new user account to **admin**.
  - Back in the **Admin** panel, click on **Identity..Projects** again.  Click on **Modify Users** next to the StackMonkey project and then assign the **stackmonkey** user to the **StackMonkey** project.
  - Log out of the system and then log back in as the **stackmonkey** user.  You should still see the **Admin** tab to the left and the **StackMonkey** project should be highlighted in the pulldown at the top left.

*Note: The StackMonkey user requires admin access to OpenStack so it can gather the capabilities and load of the hypervisors.  If you are concerned about this, you may disable the admin role for the StackMonkey user.*

Next, you'll need to launch an Ubuntu backed instance. If you don't have an Ubuntu image installed on your OpenStack cluster, follow these steps:

  - this
  - that
  - other
  
Now prepare to launch the instance by following these steps:

  - Create a key pair for ssh access to the instance.
  - Click on the **Project** tab to the far left and then click on **Compute..Instances**. To the right, click on the **Create Instance** button.  The create instance dialog should appear.
  - Name the instance **StackMonkey VA** and then click on **Boot From** and select the Ubuntu image you just installed.

Finally, you'll need to enter the following script in the post creation field:

    #cloud-config
    hostname: stackmonkey-va
    manage_etc_hosts: true
    runcmd:
     - [ wget, "http://goo.gl/KJH5Sa", -O, /tmp/install.sh ]
     - chmod 755 /tmp/install.sh
     - /tmp/install.sh

Click on the **Launch Instance** button to launch the appliance.  You can monitor the instance's build state by refreshing the console log.

### Configuration
Once the instance has been started you can access the appliance's UI by entering something like the following into your browser:

    http://10.0.47.2/


#### Shell Access
You can login to the appliance via ssh by using the key you created earlier.  Enter the following to ssh into the instance, assuming your appliance is running at 10.0.47.2 and you named the ssh key stackmonkey:

    ssh -i ~/.ssh/stackmonkey-pem ubuntu@10.0.47.2

Once you are logged in, you can access the command line client's help by changing directories and running the manage app:

    cd /var/www/utterio/
    ./manage.py --help
    

#### Admin Account
Start by creating an administrator account.  Enter the username and password (twice) to use for the admin account and then click the **Create Admin Account** button to create the account.

![Create an admin account.](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/photo.png)

Note: If you lose the login information to the appliance, you can use the command line to reset the admin account:

     ./manage.py admin -f true


### Security
From a security standpoint, the system should be reasonably secure against bad actors.  It's also reasonable to expect there are holes in that logic. Here is a short list of security features that have been built into the system:

  - Pool controllers use Google federated auth, store no passwords and can utilize two factor authentication.
  - The pool DOES NOT receive or store credentials related to an appliance's SSL tunnel or Coinbase account.
  - The  appliance's Coinbase API tokens use method level permissions and should be set to address creation only.
  - SSL tunnels are provided by the Ngrok service at [https://ngrok.com/](https://ngrok.com/). Ngrok is Open Source.
  - SSL tunnels DO NOT relay or store information related to logins, pool tokens or Coinbase credentials.
  - Bitcoin payment callbacks are handled exclusively between the appliance and Coinbase using tokens.
  - Instances can only be started by callbacks from Coinbase carrying those coin specific tokens.
  - Custom callback addresses can be used to slightly increase anonymization when provisioning servers for users.
  - Private appliance groups provide increased trust between entities and keep bad actors off certain appliances.

Obviously, certain aspects of system security can be adversely affected when considering the fact strangers are providing infrastructure services to other strangers.  Weird shit is going to happen and is expected on the StackMonkey pool.  Consider this your fair warning!

### Development
If you are doing development on this project, touch a file named **DEV** in the root directory to turn on the development debug configuration:

	cd ~/code/utterio/utter-va/
    touch DEV

If you are doing development on the project, you can start either the single threaded Flask server, or a Gunicorn multithreaded server.  Use the **--gunicorn** flag to start the Gunicorn server:

    ./manage.py serve --gunicorn true

The Gunicorn server will need to be manually restarted to reload certain files and logs to the **logs** directory.

In addition to manually starting the web server, you'll also need to do manual starts of the Ngrok tunnel during dev:

    ngrok -config tunnel.conf start utterio

If you are doing dev or testing on the appliance, you are more than welcome to join the [developer discussion channel](https://gitter.im/StackMonkey/utter-va) on Gitter.  It's likely we're going to need your assistance sooner than later.

I appreciate you being here!

K