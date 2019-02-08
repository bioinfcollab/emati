/**
 * Dynamic behavior relating to the searchbar.
 */


$(document).ready(function() {
    // Hide the loading icon by default
    $("#search-loading-icon").hide();

    // Show the loading icon after submitting the search query
    $("#search-submit-button").click(showLoadingIcon);
});


/**
 * Hides the submit button and replaces it 
 * with a loading icon.
 */
function showLoadingIcon(event) {
    $("#search-submit-button").hide();
    $("#search-loading-icon").show();
}