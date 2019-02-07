/**
 * Used to like an article. Makes the button appear green and
 * tells the backend to log this 'like' event. This function
 * should be attached to the click event of a like button.
 */
function log_like() {
    const likeButton = $(this);
    const dislikeButton = $(this).siblings(".dislike-button");

    // Provide visual feedback immediately
    likeButton.toggleClass("active");
    if (likeButton.hasClass("active") == dislikeButton.hasClass("active")) {
        dislikeButton.removeClass("active");
    }

    // Tell the backend to dislike this article
    $.ajax({
        url: likeButton.attr("url"),
        method: "POST",
    });
}


/**
 * Used to dislike an article. Makes the button appear red and
 * tells the backend to log this 'dislike' event. This function 
 * should be attached to the click event of a dislike button.
 */
function log_dislike() {
    const dislikeButton = $(this);
    const likeButton = $(this).siblings(".like-button");
    
    // Provide visual feedback immediately
    dislikeButton.toggleClass("active");
    if (likeButton.hasClass("active") == dislikeButton.hasClass("active")) {
        likeButton.removeClass("active");
    }

    // Tell the backend to dislike this article
    $.ajax({
        url: dislikeButton.attr("url"),
        method: "POST",
    });
}


/**
 * Attaches the logging of likes and dislikes to the click-events
 * of the respective buttons. This function should be called each
 * time new recommendations are inserted on the page.
 */
function attach_feedback_logging() {
    // Detach possibly connected click events and reattach them 
    // again to avoid duplicate triggering.
    $(".like-button").off('click').on('click', log_like);
    $(".dislike-button").off('click').on('click', log_dislike);
}


$(document).ready(function() {
    attach_feedback_logging();
});