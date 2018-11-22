$(document).ready(function() {

    $("#consent-checkbox").prop("checked", false);
    $("#consent-button").addClass("button-disabled");

    $("#consent-checkbox").click(function(e) {
        // Toggle the submit button on/off
        $("#consent-button").toggleClass("button-disabled");
        if (this.checked) {
            $("#consent-button").prop('disabled', false);    
        } else {
            $("#consent-button").prop('disabled', true);
        }
    })

});
