## Welcome to Utter.io and StackMonkey!
[![Gitter chat](https://badges.gitter.im/StackMonkey/utter-va.png)](https://gitter.im/StackMonkey/utter-va)

We currently need individuals familiar with [OpenStack](http://openstack.org/) to [install and run the appliance](https://www.stackmonkey.com/appliances/new/) for the beta test. This software, collectively known as [Utter.io](https://www.stackmonkey.com/), allows you to sell virtualized instances for Bitcoin:

[![Instance Payment](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/start_instance_thumb.png)](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/start_instance.png) 


Utter.io is like AirBnb for excess compute: The utter.io project provides fast location and provisioning of compute resources within a cooperative set of systems managed by [OpenStack operators](http://superuser.openstack.org/). Resource accounting inside the network is settled with [Bitcoin](https://bitcoin.org/) and purchases of compute instances can be made by users without an account. Additionally, groups of operators can form adhoc [hybrid clouds](http://en.wikipedia.org/wiki/Cloud_computing#Hybrid_cloud), allowing fast scaling and sharing of excess compute resources between trusted entities.  If you are familiar with cloud terminology, this idea may be one possible solution to some of the challenges in achieving a global [cloud federation](http://www.datacenterknowledge.com/archives/2012/09/17/federation-is-the-future-of-the-cloud/).

Crypto currency technologies can bring a new category to the existing cloud offerings of **compute**, **storage**, and **network**.  That new category is **trust**. While conversations about how crypto currencies affect our financial systems are definitely interesting, paying for **compute**, **storage** and **network** with stored **trust** is an awe inspiring vision of the future.

This peek into the future of [commodity compute](http://en.wikipedia.org/wiki/Commodity_computing) can be seen by visiting the [StackMonkey compute pool](https://www.stackmonkey.com/). StackMonkey is a demonstrative cooperative intended to be the Wild West of compute pools (given it's the first one) and built for use by hackers, crackers, security researchers, devs, do-it-yourselfers, and the communities and technologies they develop from it.

All code providing basic infrastructure services to the project will be Open Source and will be licensed under the [MIT License](http://opensource.org/licenses/MIT).

### Project Components
A set of three Open Source repositories provide the project's functionality: [utter-va](https://github.com/StackMonkey/utter-va), [utter-pool](https://github.com/StackMonkey/utter-pool) and [utter-exchange](https://github.com/StackMonkey/utter-exchange). The utter-va virtual appliance provided by this repository builds an instance which runs on top of an OpenStack cluster. The appliance controls the OpenStack cluster's capabilities, advertises instances for sale on a central pool controller running utter-pool and launches instances when payments are observed on the [Bitcoin Blockchain](https://en.bitcoin.it/wiki/Block_chain) through callbacks made by [Coinbase](https://coinbase.com/).

The first compute pool is hosted on [AppEngine](https://appspot.com) and runs the [StackMonkey pool](https://www.stackmonkey.com). The expected beta launch date of the StackMonkey pool is no later than **August 31, 2014**, with minor pre-beta releases done weekly until then.  After launch, individuals will be able to purchase instances for Bitcoin from the site. Please note you will need [register an account](https://www.stackmonkey.com/login/) on StackMonkey if you want to sell instances, but buying them doesn't require one.

The utter-exchange component will be completed at a later date, probably in mid-2015. The exchange will serve as a clearing house for compute put up for sale on the pool controllers. Keep in mind there is an opportunity to run [more pools](https://github.com/stackmonkey/utter-pool), so get motivated!  The exchange will operate as a [DAC](https://en.bitcoin.it/wiki/Distributed_Autonomous_Community_/_Decentralized_Application) once the technologies required to create it have been completed.  You can expect a crypto currency to be launched for the project. Both the currency and compute assets managed by the network will be connected to the crypto markets.

### Requirements
The virtual appliance requires a running OpenStack cluster.  If you don't have an OpenStack cluster already running, fear not!  You may follow the instructions for [Installing OpenStack in 10 Minutes](http://www.stackgeek.com/guides/gettingstarted.html) on the [StackGeek website](http://stackgeek.com/).

Once you have OpenStack installed, you'll need to create or have the following service accounts available:

  - a [StackMonkey](https://www.stackmonkey.com/login/) account (signup takes 1 minute)
  - a [Coinbase](https://coinbase.com/signup?r=52a9c6bf937ab6453a00001e&utm_campaign=user-referral&src=referral-link) account (signup takes 2 minutes)
  - an [Ngrok](https://ngrok.com/) account (signup takes 1 minute)


### Watch the Install Video
The [following video](https://vimeo.com/91805503) will step you through installing the virtual appliance on your OpenStack cluster.  If you have any questions about the install, you can head over to [StackMonkey's Appliance Gitter](https://gitter.im/StackMonkey/utter-va) for the group chat.

[![Instance Payment](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/video_thumb.png)](https://vimeo.com/100944207) 

### Automated Install
This is by far the easiest way to install an appliance.  If you've previously followed StackGeek's [Installing OpenStack in 10 Minutes](http://www.stackgeek.com/guides/gettingstarted.html) guide, you can run the appliance install script located in the [Icehouse](https://github.com/StackGeek/openstackgeek/tree/master/icehouse) directory:

    ./openstack_stackmonkey_va.sh

The script automatically creates a user and project for the virtual appliance, sets the security group rules for the project, and then launches the appliance on the OpenStack cluster.  SSH keys are automatically created for accessing the appliance's console and a URL will be spit out at the end for accessing the web UI.  

Once the script completes, you can skip to the configuration section below.

***Note***: It may be possible to run this script on an existing OpenStack cluster not installed with the StackGeek scripts.

### Manual Install
If you have previously installed OpenStack, you can manually start a virtual appliance from the **Horizon UI**.  Begin by logging into OpenStack with an administrative account and then following these steps:

  - Click on the **Admin** tab to the far left and then click on **Identity Panel..Projects**. To the right, click on the **Create Project** button and then enter a new project name called **stackmonkey** in the name field.  Click on **Create Project** below to create the new project.
  - Back in the **Admin** panel, click on **Users**.  To the right, click on the **Create User** button and then create a new user called **stackmonkey** and set the user's password.  Set the primary project to **stackmonkey** and set role of the new user account to **admin**.
  - Log out of the system and then log back in as the **stackmonkey** user.  You should still see the **Admin** tab to the left and the **stackmonkey** project should be highlighted in the pulldown at the top left.

*Note: The StackMonkey user requires admin access to OpenStack so it can gather the capabilities and current load on the hypervisors.  If you are concerned about this from a security standpoint, you may disable the admin role for the StackMonkey user. The net effect will be a decrease in the number of instances your appliance can sell.*

#### Install an Ubuntu Image
The appliance requires an Ubuntu backed instance. If you don't have an Ubuntu image installed on your OpenStack cluster, follow these steps:

  - Click on the **Admin** tab to the far left and then click on **System Panel..Images**. Click on the **Create Image** button to the top right.
  - Name the image **Ubuntu Trusty 14.04LTS** and then paste **[http://goo.gl/u2IBP9](http://goo.gl/u2IBP9)** into the location field.
  - Select the **QCOW2** format in the pulldown and make the image public if you want to share it with other OpenStack users.
  - Click **Create Image** to create the new boot image.

#### Create a Keypair
You need to create a key pair that you can use to access the virtual appliance's command line console.  Follow these steps to create the key:

  - Click on the **Project** tab to the far left and then click on **Compute..Instances**. Click on **Access & Security** and then click on the **Key Pairs** tab at the top.
  - Click **Create Key Pair** and name the key pair **stackmonkey**.  Click **Create Key Pair** to create the key pair.  The private key will be downloaded to your local machine.

You need to move the private key into your **.ssh directory** (or similar for Windows) and then change the permissions on it:

	cd ~/Downloads/
	mv stackmonkey.pem ~/.ssh/
    chmod 600 ~/.ssh/stackmonkey.pem

We'll use the key in a minute to ssh into the appliance for maintenance tasks and viewing logs.

#### Set the Access Rules
The instances being sold by the appliance will need unrestricted access from the Internet if they have publicly accessible addresses. For now, the appliance does not manage the security groups, so you need to open up the default group to allow all access to the instances you will be starting.  Follow these steps to setup your access rules for the appliance:

  - Click on the **Project** tab to the far left and then click on **Compute..Access & Security**. 
  - Click on the **Security Groups** tab at the top.  To the right, click on the **Create Security Group** button.  
  - Name the security group **'appliance'** and enter a short description.  Click **Create Security Group** to create the group.
  - Click the **Manage Rules** button to the right in the **appliance** security group row.  Click **Add Rule** and then enter the number **'22'** (ssh) in the port field.  Click **Add**.  Repeat this step and enter the number **'80'** (http) in the port field instead.  Click **Add** again.
  - Click the **Manage Rules** button again, but this time click on the **Rule** pulldown and select **Custom ICMP Rule**.  Enter the number '-1' in **both** the **Type** and **Code** fields.  Click **Add** to add the rule.

Your **appliance** security group rules should now look like this:

[![OpenStack Groups](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/appliance_groups_thumb.png)](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/appliance_groups.png)
  
Now follow these steps to set up the access rules for the instances that will be started on the cluster by the appliance:

  - Click on the **Project** tab to the far left and then click on **Compute..Access & Security**.
  - Click the **Manage Rules** button to the right in the **default** security group row.  
  - Delete any existing rules for the default group by clicking on **Delete Rule** in any of the existing rule's rows.
  - Click **Add Rule** and then select **Custom TCP Rule** from the **Rule** pulldown and **Port Range** from the **Open Port** pulldown.
  - Enter the number **'1'** in the **From Port** field. Enter the number **'65535'** in the **To Port** field. Click **Add**.
  - Repeat the previous two steps, but this time select **Custom UDP Rule** from the **Rule** pulldown.  Enter the same numbers for the range.
  - Click **Add Rule** and then select **Custom ICPMP Rule** from the **Rule** pulldown.  
  - Enter the number **'-1'** in **both** the **Type** and **Code** fields.  Click **Add** to add the rule.

Your **default** security group rules should now look like this:

[![OpenStack Groups](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/default_groups_thumb.png)](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/default_groups.png)

#### Create a Flavor for the Appliance
The appliance needs about 8GB of drive space for caching boot images. To create a new flavor that is the right size for for the appliance, do the following:

  - Click on the **Admin** tab to the far left and then click on **System Panel..Flavors**.  Click the **Create Flavor** button at the top right.
  - Name the flavor **'m512.v1.d8'**. For **VCPUs** put the number **'1'**.  For **RAM** put **'512'**.  For **Root Disk GB** put **'8'** and then click **Create Flavor** to create the new flavor.
 
[![OpenStack Flavor](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/flavor_thumb.png)](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/flavor.png)

#### Start the Instance
Now all the components of the instance have been created, you can launch an instance which will configure itself into a StackMonkey virtual appliance.  Follow these instructions to launch the instance:

  - Click on the **Project** tab to the far left and then click on **Compute..Instances**. To the right, click on the **Launch Instance** button.
  - Name the instance **'StackMonkey VA'** and then click on the **Flavor** pulldown and select the **m512.v1.d8** flavor.
  - Click on the **Instance Boot Source** pulldown at the bottom and select **Boot from image**.  Under **Image Name**, select the **Ubuntu Trusty 14.04LTS** image you installed earlier.
  - Click on the **Access & Security** tab at the top.  Use the **Key Pair** pulldown to select the **stackmonkey** key pair you generated earlier.  
  - In the same tab, check the **appliance** security group, and uncheck the **default** group.
  - Click on the **Post-Creation** tab at the top.  
  
In the Customization Script text area that appears in the modal, paste the following exactly as shown:
      
    #cloud-config
    hostname: stackmonkey-va
    manage_etc_hosts: true
    runcmd:
     - [ wget, "http://goo.gl/KJH5Sa", -O, /tmp/install.sh ]
     - chmod 755 /tmp/install.sh
     - /tmp/install.sh

Click on the **Launch** button to launch the appliance.  You can monitor the instance's build state by refreshing the console log tab viewable by clicking on the instance name in the instance list. 

The appliance takes about 10 minutes to build.  

### Accessing the Appliance
Once the appliance is running, you can access it by its IP address.  This can be found in the Horizon UI of OpenStack, next to the instance.  Here's an example:

[![Appliance IPs](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/appliance_ip_thumb.png)](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/appliance_ip.png)

Build a URL of the IP address of the appliance and enter it into your browser's address bar:

    http://10.0.47.3/

Remember, it takes about 10 minutes for the appliance to build.  In the meantime, log in via ssh.

#### Shell Access
You can login to the appliance via ssh by using the key you created earlier. Assuming your appliance is running at **10.0.47.3** and you named the ssh key **stackmonkey** you may enter enter the following to ssh into the instance:

    ssh -i ~/.ssh/stackmonkey.pem ubuntu@10.0.47.3

If you've previously accessed this IP with ssh before, or you rebuild the appliance later, you may need to clear it from your **known_hosts** file: 

    ssh-keygen -R 10.0.47.3
    
Once you are logged in, you can access the command line client's help by changing directories and running the manage app:

    cd /var/www/utterio/
    ./manage.py --help
    
There are a set of cron jobs that run periodically.  You may view them by entering the following:

    crontab -l

#### Admin Account
Once the web-based UI comes up, you start things off by creating an administrator account.  Enter the username, password, and  password again to create an account. Click the **Create Admin Account** button to create the account and automatically sign in.

[![Create an admin account.](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/admin_thumb.png)](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/admin.png)

If you lose the login information to the appliance, you can use a command to reset the admin account:

     ./manage.py admin -f true

***Note:*** Keep in mind that the appliance URL is not intended to be shared with others.  While connections from the outside are encrypted over the SSL tunnel, and the URL of the appliance is never publicly shared, your local access to the UI via IP address is neither secured nor encrypted.  This will be addressed in later version.  More information about appliance security is located at the bottom of this document.

### Appliance Configuration
Once you've logged into the appliance, click on the **Appliance** tab at the top left.  You'll see a few warning messages pop up and go away in the bottom right corner.  There should be some notifications next to a few of the tabs to the left, indicating the appliance isn't functional yet. Here's a view of that configuration screen with warnings:

[![Create an admin account.](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/appliance_configuration_thumb.png)](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/appliance_configuration.png)

#### Pool API Token
Click the **Register API Token** button to register the appliance with the pool.  If you haven't signed up for the **StackMonkey pool** yet, you will be prompted by Google to allow access to your account from the site.  Once you have authenticated with the site, you'll be presented with a new appliance form:

![Create an admin account.](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/new_appliance.png)  
  
Enter a name for the appliance and leave it in the **Public** group for now.  Click on **Create Appliance** to add it to your account.  You may also want to take a moment and [setup two factor authentication](https://www.stackmonkey.com/settings/) on StackMonkey.

#### Coinbase Tokens
Navigate to [Coinbase](https://coinbase.com/signup?r=52a9c6bf937ab6453a00001e&utm_campaign=user-referral&src=referral-link) and sign up for a new account. Coinbase will email you a confirmation link which you will need to click to complete your login.

  - To create an API key, click on the **login pulldown** at the top right, then click on **settings**.
  - Click on the **API** tab at the top and then click on the **New API Key** button to the right.
  - You'll be prompted for a password or two factor auth key.  Enter whichever is applicable and click **Verify** to continue.

When you create a new API key on Coinbase, you can specify what actions it can perform on your account.  Given Bitcoin is like money, you'll want to be very careful about the permissions you give external applications.  The StackMonkey appliance only needs access to **creating new Bitcoin addresses** for your account.  This allows it to create new addresses for instances, and watch payments to those addresses by individuals.

Proceed by ensuring **HMAC (Key + Secret)** is selected at the top.  Check the **My Wallet** checkbox and then check the **addresses** checkbox under permissions.  Verify there are no other method permissions checked, other than addresses:

[![Create an admin account.](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/coinbase_thumb.png)](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/coinbase.png) 

Proceed with these steps to finish adding the Coinbase API keys to the appliance:

  - Click on **Create** to create the new API key and then click on the **Enable** link back in the API key list.  
  - Go check your email again for a verification code and copy it into your paste buffer.  
  - Back on the Coinbase page, paste the code into the **API Key details** prompt and then click **Verify**.
  - Click on the **Key Link** just to the right of the **enabled** status for the key. You'll be prompted again for a password/2FA key.
  - Enter the appropriate credentials and then click **Verify** again.
  - Copy the **API Key** into your paste buffer and then switch back to the **StackMonkey Virtual Appliance** page.
  - Paste the key into the **Coinbase Client ID** field.  Switch back to the **Coinbase** page.
  - Copy the **API Secret** into your paste buffer and then switch back to the **StackMonkey Virtual Appliance** page.
  - Paste the key into the **Coinbase Client Secret** field. 
  - Click on **Save Configuration** at the bottom.
  
If you need to see the **Coinbase Client Secret** from the appliance page again, you can click on the **eye** icon next to the **Client ID** field.

#### Ngrok Token
Setting up the Ngrok token takes less than 30 seconds, given you have a Github account.  Begin by following these steps:

  - Click the **cog** icon next to the **Ngrok Token** field.  The Ngrok site will appear.
  - Click on **Login with Github**.  Github will ask you to approve the Ngrok site's access to your account.
  - Once you've tied Ngrok to your Github account, you'll be presented with an **auth token** at the top of the page.
  - Click the **copy** button to copy the token and then switch back to the **StackMonkey Virtual Appliance** page.
  - Paste the token into the **Ngrok Token** field and then click **Save Configuration**.
  
The Ngrok SSL tunnel will be established as soon as you've completed the rest of the configuration.  The lack of a warning indicator next to the **Appliance** tab will be your cue that the appliance is ready to serve instances.

#### Service Location
Use the map to set the physical location of the OpenStack cluster on top of which the appliance is running. If you want to be somewhat private about your exact location that's not a problem, but you should try to set the location to something reasonably close to where you live.  If you live in the country, set it to a few miles from your home.  If you live in the city, set it to a few blocks away.

[![Service Location](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/service_location_thumb.png)](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/service_location.png) 

Click on **Save Configuration** at any time to save the current service location.

The location you set in the appliance will be used by the system to provide geolocation based instances to users.  Setting your location to something a large distance from your location will eventually be detected by the pool and its users.  The lesson here is, be mostly honest about your location or simply don't use the appliance to sell instances!

#### OpenStack Setup
To set up the appliance's OpenStack connection, you'll need to download a configuration file from the OpenStack interface:

  - Log into your OpenStack cluster using the **stackmonkey** user you created earlier.
  - Click on the **Project** tab to the far left and then click on **Compute..Access & Security**.
  - Click on the **API Access** tab at the top.  Click on the **Download OpenStack RC File** button to the right.

Switch back to the appliance's page and do the following:

  - Click on the **Click or drag here to upload your RC file** button at the top. Select the file you just downloaded, and then click on the system dialog's **Open** button at the bottom right.
  - Enter the password you used earlier creating the **stackmonkey** user and then click **Save Configuration**.
  
Here's a screenshot of a completed OpenStack setup for reference:

[![Openstack Setup](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/openstack_thumb.png)](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/openstack.png) 

### Using the Appliance
Using the appliance is fairly self explanatory.  Click on the **Instances** tab to the left and then click on the **Start** or **Payment** buttons to the right of an instance for instructions on starting them.  You'll need to [configure a wisp on StackMonkey](https://www.stackmonkey.com/wisps) for the appliance to use to boot your instances.  There will be more information forthcoming on using the appliance to start and sell instances, so stay tuned to the [blog on StackMonkey](https://www.stackmonkey.com/blog/)!

[![Start Instances](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/start_instance_thumb.png)](https://raw.githubusercontent.com/StackMonkey/utter-va/master/webapp/static/img/readme/start_instance.png) 

### Security
From a security standpoint, the ***system management portions*** of the project should be reasonably secure against bad actors.  It's also reasonable to expect there are holes in that logic at this early stage of the project. Here is a short list of security features that have been built into the system:

  - Pool controllers use Google federated auth, store no passwords and provide two factor authentication.
  - The pool DOES NOT know about or store credentials related to an appliance's SSL tunnel or Coinbase account.
  - The  appliance's Coinbase API tokens use method level permissions and are suppose to be set to address creation only.
  - SSL tunnels are provided by the Open Source based Ngrok service at [https://ngrok.com/](https://ngrok.com/).
  - SSL tunnels DO NOT relay or store information related to logins, pool tokens or Coinbase credentials.
  - Bitcoin payment callbacks are handled exclusively through the Ngrok SSL tunnel and Coinbase.
  - Instances can only be started by callbacks from Coinbase to the appliance carrying those coin specific tokens.
  - Custom callback addresses can be used to slightly increase anonymization when provisioning servers for users.
  - Private appliance groups provide a way to leverage trust between entities helping keep bad actors off your appliances.

Obviously, certain aspects of system security can be adversely affected when considering the fact strangers are providing infrastructure services to other strangers.  Weird shit is going to happen, and is expected on the StackMonkey pool.  If you don't like the idea of that, then don't use it.

To mitigate harm to the system and outside users, the plan is allow the community to provide security services for itself. White lists, black lists, voting buttons, voting addresses, karma on payment addresses, bitcoin contracted bounties, and anything and everything we need to do to ensure we get a good night's rest will be explored and tested. Expect data feeds of all server starts or callbacks, ask prices, bids, URLs used for boots, and general appliance statistics.  All this data can and will be used in an open and transparent way to provide reliable and trustworthy infrastructure.

Remember, infrastructure is meant to be [open and transparent](http://www.stackgeek.com/blog/kordless/post/a-code-of-trust). This project makes that a priority.

### Development
If you are interested in doing development on this project, touch a file named **DEV** in the root directory to turn on the development debug configuration:

	cd ~/code/utterio/utter-va/
    touch DEV

In dev mode, you can start either the single threaded Flask server, or a Gunicorn multithreaded server.  Use the **--gunicorn** flag to start the Gunicorn server:

    ./manage.py serve --gunicorn true

The Gunicorn server will need to be manually restarted to reload certain files and logs to the **logs** directory.

In addition to manually starting the web server, you'll also need to do manual starts of the Ngrok tunnel during dev:

    ngrok -config tunnel.conf start utterio

If you are doing dev or testing on the appliance, you are more than welcome to join the [developer discussion channel](https://gitter.im/StackMonkey/utter-va) on Gitter.

I appreciate you being here!

Kord
