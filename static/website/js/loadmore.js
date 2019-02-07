$(document).ready(function() {
    // Add the appropriate funcitonality to the button
    $("#load-more-button").click(loadMore);
});


/**
 * Called by clicking on the "Load more"-button.
 */
function loadMore(event) {
    event.preventDefault();

    var loadMoreButton = $(this);
    var params = getUrlParameters();
    params.offset = getOffset();

    $("#load-more-button").hide();
    $("#load-more-spinner").show();

    // Request more content from the server
    $.ajax({
        url: loadMoreButton.attr("href"),
        method: "GET",
        data: params,
        success: function(data) {
            // `data` contains its own #load-more-container
            // Therefore we simply overwrite the old container
            // with everything we just received.
            $("#load-more-container").replaceWith(data);

            // Assign the function to this newly inserted button
            $("#load-more-button").click(loadMore);
            $("#load-more-button").show();

            // Assign the like/dislike function to the new articles
            attach_feedback_logging();
        },
        error: function(xhr, ajaxOptions, thrownError) {
            // Something went wrong. Log the error.
            console.log(xhr.status);
            console.log(thrownError);
        },
        complete: function() {
            // No matter what happened, we need to hide the spinner again
            $("#load-more-spinner").hide();
        }
    })
}


/**
 * Returns the number of articles on this page.
 */
function getOffset() {
    return $(".article").length;
}


/**
 * Reads the GET parameters of the currently viewed page. Parses them into
 * key,value-pairs and returns them as a dictionary.
 */
function getUrlParameters() {
    var sPageURL = decodeURIComponent(window.location.search.substring(1)),
        sURLVariables = sPageURL.split('&'),
        params = {},
        i;

    for (i = 0; i < sURLVariables.length; i++) {
        [key, value] = sURLVariables[i].split('=');
        params[key] = value;
    }
    return params;
};