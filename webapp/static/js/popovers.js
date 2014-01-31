$().ready(function() {
  // help popovers
  $("#payment-address").popover({ 
    title: '<strong>Payment Address</strong>', 
    content: "<p>Enter a Bitcoin payment address where you wish to receive Bitcoin payments. This should be an address you have generated with a Bitcoin client or a wallet hosting service. You can use the <span class='glyphicon glyphicon-link'></span> button to signup for a Blockchain account if you don't have a wallet. <strong>Using an address you do not control will result in a loss of funds.</strong></p>", 
    html: true, 
    trigger: "hover",
    placement: "left"
  }).blur(function () {
    $(this).popover('hide');
  });
  $("#api-token-hover").popover({ 
    title: '<strong>API Token</strong>', 
    content: '<p>Click the <span class="glyphicon glyphicon-refresh"></span> button below to generate a new API token.  If the <strong>Register API Token</strong> button is orange, click on it to link the current API token to your account. Please note you cannot manually enter an API token on this page.</p>', 
    html: true,
    trigger: "hover",
    placement: "left"
  }).blur(function () {
    $(this).popover('hide');
  });
  $("#ngrok-token").popover({ 
    title: '<strong>SSL Tunnel Token</strong>', 
    content: "<p>If this appliance's IP address is not publicly accessable, use the <span class='glyphicon glyphicon-cog'></span> button to access the ngrok.com website to get a token.  If an ngrok.com token is present, a URL will be generated and placed in the <strong>Service URL</strong> field below after you save the configuration.</p>", 
    html: true,
    trigger: "hover",
    placement: "left"
  }).blur(function () {
    $(this).popover('hide');
  });
  $("#map").popover({ 
    title: '<strong>Service Location</strong>', 
    content: "Use the map to drag the pin to indicate the geo location of the OpenStack cluster this appliance manages.  If you are unsure of the physical location of the cluster, use the default location obtained from the geo IP lookup.</p>", 
    html: true,
    trigger: "hover",
    placement: "left"
  }).blur(function () {
    $(this).popover('hide');
  });
  $("#appliance-settings").popover({ 
    title: '<strong>Warning</strong>', 
    content: "<p>This appliance needs to be configured with a payment address and SSL token.</p>", 
    html: true,
    trigger: "hover",
    placement: "bottom"
  }).blur(function () {
    $(this).popover('hide');
  });
  $("#openstack-settings").popover({ 
    title: '<strong>Warning</strong>', 
    content: "<p>A connection to an OpenStack cluster cannot be made.</p>", 
    html: true,
    trigger: "hover",
    placement: "bottom"
  }).blur(function () {
    $(this).popover('hide');
  });
  $("#systems-settings").popover({ 
    title: '<strong>Warning</strong>', 
    content: "<p>This appliance needs a minimum of one flavor and one image to provide service.</p>", 
    html: true,
    trigger: "hover",
    placement: "bottom"
  }).blur(function () {
    $(this).popover('hide');
  });
});