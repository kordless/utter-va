$().ready(function() {
  // help popovers for appliance setup
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
  $("#flavors-settings").popover({ 
    title: '<strong>Warning</strong>', 
    content: "<p>This appliance needs a minimum of one flavor enabled to provide service.</p>", 
    html: true,
    trigger: "hover",
    placement: "bottom"
  }).blur(function () {
    $(this).popover('hide');
  });

  // instance detail page
  $(".instance-state").popover({
    content: $(".instance-state").attr("data-state-string"),
    html: true,
    trigger: "hover",
    placement: "bottom"
  }).blur(function () {
    $(this).popover('hide');
  });
});