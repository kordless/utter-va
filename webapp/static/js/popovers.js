$().ready(function() {
  // help popovers
  $("#hover-cb-api-secret").popover({ 
    title: '<strong>Coinbase Client Secret</strong>', 
    content: '<p>Enter your Coinbase <strong>API secret</strong> here.</p>', 
    html: true, 
    trigger: "hover",
    placement: "top"
  }).blur(function () {
    $(this).popover('hide');
  });
  $("#hover-cb-api-key").popover({ 
    title: '<strong>Coinbase Client ID</strong>', 
    content: '<p>Enter your Coinbase <strong>API Key</strong>. Toggle visibility of the ' +
              '<strong>API Secret</strong> with the <span class="glyphicon glyphicon-eye-open"></span> icon.</p>', 
    html: true, 
    trigger: "hover",
    placement: "top"
  }).blur(function () {
    $(this).popover('hide');
  });
  $("#hover-ngrok-token").popover({ 
    title: '<strong>Ngrok Tunnel Token</strong>', 
    content: "<p>Use the <span class='glyphicon glyphicon-cog'></span> button to access the ngrok.com website to get a token.</p>", 
    html: true,
    trigger: "hover",
    placement: "top"
  }).blur(function () {
    $(this).popover('hide');
  });
  $("#hover-api-token").popover({ 
    title: '<strong>API Token</strong>', 
    content: '<p>Click the <span class="glyphicon glyphicon-refresh"></span> button to the right to generate a new ' +
              'API token.  If the <strong>Register API Token</strong> button is orange, click it to link ' +
              'the current API token to your account.</p>', 
    html: true,
    trigger: "hover",
    placement: "top"
  }).blur(function () {
    $(this).popover('hide');
  });
  $("#map").popover({ 
    title: '<strong>Service Location</strong>', 
    content: 'Use the map to drag the pin to indicate the geo location of the OpenStack cluster this appliance ' +
              'manages.  If you are unsure of the physical location of the cluster, use the default location ' +
              'obtained from the geo IP lookup.</p>', 
    html: true,
    trigger: "hover",
    placement: "top"
  }).blur(function () {
    $(this).popover('hide');
  });
  $("#appliance-settings").popover({ 
    title: '<strong>Warning</strong>', 
    content: "<p>This appliance needs to be configured with a Coinbase account and Ngrok token.</p>", 
    html: true,
    trigger: "hover",
    placement: "bottom"
  }).blur(function () {
    $(this).popover('hide');
  });
  $("#openstack-settings").popover({ 
    title: '<strong>Warning</strong>', 
    content: "<p>Could not establish a connection with the OpenStack cluster.  Check your settings!</p>", 
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